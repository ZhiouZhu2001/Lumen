"""Create a private consistent dump and verify it in a disposable offline container."""

import argparse
import asyncio
import csv
import hashlib
import io
import json
import os
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db import make_engine


class BackupError(Exception):
    pass


def private_directory(path):
    path = Path(path).absolute()
    if path.is_symlink() or path.resolve() != path:
        raise BackupError("Backup destination must not traverse symbolic links")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            check=True,
        )
        sid = next(csv.reader(io.StringIO(result.stdout)))[1]
        if not sid.startswith("S-1-"):
            raise BackupError("Cannot identify the current backup owner")
        import ctypes
        from ctypes import wintypes

        security = ctypes.WinDLL("advapi32", use_last_error=True)
        convert = security.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.DWORD),
        ]
        convert.restype = wintypes.BOOL
        apply = security.SetFileSecurityW
        apply.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
        apply.restype = wintypes.BOOL
        descriptor = ctypes.c_void_p()
        if not convert(
            f"D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)", 1, ctypes.byref(descriptor), None
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not apply(str(path), 0x80000004, descriptor):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            release = ctypes.WinDLL("kernel32").LocalFree
            release.argtypes = [ctypes.c_void_p]
            release.restype = ctypes.c_void_p
            release(descriptor)
    else:
        if path.stat().st_uid != os.geteuid():
            raise BackupError("Backup destination must belong to the current user")
        path.chmod(0o700)
    return path


@contextmanager
def private_file(path, mode="xb"):
    with Path(path).open(mode) as handle:
        if os.name != "nt":
            os.chmod(path, 0o600)
        yield handle


async def docker(*args, stdout=None):
    process = await asyncio.create_subprocess_exec(
        "docker",
        *args,
        stdout=stdout if stdout is not None else asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output, _ = await process.communicate()
    if process.returncode:
        # Docker/SQL diagnostics may contain connection or reader data. Keep the
        # public failure generic; a failed archive is never labeled verified.
        raise BackupError("A backup container command failed")
    return output.decode().strip() if output is not None else ""


def archive_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def fingerprint(connection):
    names = (
        (
            await connection.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
                )
            )
        )
        .scalars()
        .all()
    )
    quote = connection.dialect.identifier_preparer.quote
    result = {}
    await connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    await connection.execute(text("SET LOCAL DateStyle TO ISO, YMD"))
    for name in names:
        digest, count = hashlib.sha256(), 0
        query = text(
            f'SELECT row_to_json(t)::text FROM public.{quote(name)} AS t ORDER BY row_to_json(t)::text COLLATE "C"'
        )
        stream = await connection.stream_scalars(query)
        async for row in stream:
            digest.update(row.encode("utf-8") + b"\n")
            count += 1
        result[name] = {"rows": count, "sha256": digest.hexdigest()}
    return result


async def verify_archive(archive, image, database, expected, label, cap):
    name = "lumen-restore-check-" + label
    created = False
    try:
        await docker(
            "run",
            "-d",
            "--name",
            name,
            "--label",
            "com.lumen.restore=" + label,
            "--network",
            "none",
            "-e",
            "POSTGRES_USER=restore_check",
            "-e",
            "POSTGRES_PASSWORD=restore_check_only",
            "-e",
            "POSTGRES_DB=" + database,
            image,
        )
        created = True
        for _ in range(60):
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "exec",
                name,
                "pg_isready",
                "-U",
                "restore_check",
                "-d",
                database,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            if await proc.wait() == 0:
                break
            await asyncio.sleep(0.5)
        else:
            raise BackupError("Disposable restore database did not become ready")
        empty = await docker(
            "exec",
            name,
            "psql",
            "-X",
            "-At",
            "-U",
            "restore_check",
            "-d",
            database,
            "-c",
            "SELECT count(*) FROM pg_tables WHERE schemaname='public'",
        )
        if empty != "0":
            raise BackupError("Disposable public schema is unexpectedly populated")
        # Schema-filtered dumps recreate public. Remove only the empty schema
        # in this newly created, labeled offline target; never use CASCADE.
        await docker(
            "exec",
            name,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "restore_check",
            "-d",
            database,
            "-c",
            "DROP SCHEMA public",
        )
        await docker("cp", str(archive), name + ":/tmp/backup.dump")
        await docker(
            "exec",
            name,
            "pg_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-acl",
            "-U",
            "restore_check",
            "-d",
            database,
            "/tmp/backup.dump",
        )
        # Compare using the same PostgreSQL JSON representation and UTC settings
        # through the container's Unix socket; no temporary TCP port is exposed.
        actual = {}
        for table in expected:
            quote = '"' + table.replace('"', '""') + '"'
            query = f"SET TIME ZONE 'UTC'; SET DateStyle TO ISO, YMD; COPY (SELECT row_to_json(t)::text FROM public.{quote} AS t ORDER BY row_to_json(t)::text COLLATE \"C\") TO STDOUT"
            # COPY escapes characters; decode its text protocol before hashing.
            raw = await docker(
                "exec",
                name,
                "psql",
                "-X",
                "-q",
                "-U",
                "restore_check",
                "-d",
                database,
                "-c",
                query,
            )
            digest, count = hashlib.sha256(), 0
            for row in raw.splitlines():
                # COPY text escaping doubles JSON backslashes and escapes tabs.
                decoded = bytearray()
                data = row.encode("utf-8")
                i = 0
                while i < len(data):
                    if data[i] == 92 and i + 1 < len(data):
                        i += 1
                        decoded.extend(
                            {
                                92: b"\\",
                                ord("t"): b"\t",
                                ord("n"): b"\n",
                                ord("r"): b"\r",
                            }.get(data[i], bytes([data[i]]))
                        )
                    else:
                        decoded.append(data[i])
                    i += 1
                digest.update(bytes(decoded) + b"\n")
                count += 1
            actual[table] = {"rows": count, "sha256": digest.hexdigest()}
        if actual != expected:
            raise BackupError(
                "Restored table contents did not match the exported snapshot"
            )
        quarantine = False
        if "ai_daily_usage" in expected:
            # A recovered old ledger is not proof of today's unspent allowance.
            # Block this disposable recovery until reconciliation or UTC reset.
            query = f"INSERT INTO public.ai_daily_usage (id,utc_day,attempts) VALUES (1,(clock_timestamp() AT TIME ZONE 'UTC')::date,{int(cap)}) ON CONFLICT(id) DO UPDATE SET utc_day=(clock_timestamp() AT TIME ZONE 'UTC')::date,attempts=GREATEST(ai_daily_usage.attempts,{int(cap)})"
            await docker(
                "exec",
                name,
                "psql",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "restore_check",
                "-d",
                database,
                "-c",
                query,
            )
            used = await docker(
                "exec",
                name,
                "psql",
                "-X",
                "-At",
                "-U",
                "restore_check",
                "-d",
                database,
                "-c",
                "SELECT attempts FROM public.ai_daily_usage WHERE id=1",
            )
            if int(used) < cap:
                raise BackupError("Recovered budget was not blocked")
            quarantine = True
        return {
            "contents_match_snapshot": True,
            "recovered_budget_blocked": quarantine,
            "network_access": "none",
            "temporary_target_removed": True,
        }
    finally:
        if created:
            info = json.loads(await docker("inspect", name))[0]
            if info["Config"]["Labels"].get("com.lumen.restore") != label:
                raise BackupError("Restore target ownership changed; refusing removal")
            await docker("rm", "-f", "-v", name)


async def backup(args):
    settings = get_settings()
    url = make_url(settings.database_url)
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise BackupError(
            "This Compose-host backup tool requires an explicitly local database URL"
        )
    folder = private_directory(args.directory)
    label = uuid4().hex[:12]
    name = datetime.now(UTC).strftime("lumen-%Y%m%dT%H%M%SZ-") + label
    archive = folder / (name + ".dump")
    receipt = folder / (name + ".json")
    container = await docker("compose", "ps", "-q", "postgres")
    if not container or "\n" in container:
        raise BackupError("Exactly one running Compose PostgreSQL service is required")
    info = json.loads(await docker("inspect", container))[0]
    if info["Config"]["Labels"].get("com.docker.compose.service") != "postgres":
        raise BackupError("Unexpected source container")
    image = info["Config"]["Image"]
    engine = make_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            await connection.execution_options(isolation_level="REPEATABLE READ")
            async with connection.begin():
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                cluster = str(
                    await connection.scalar(
                        text("SELECT system_identifier FROM pg_control_system()")
                    )
                )
                same = await docker(
                    "exec",
                    container,
                    "psql",
                    "-X",
                    "-At",
                    "-U",
                    url.username,
                    "-d",
                    url.database,
                    "-c",
                    "SELECT system_identifier FROM pg_control_system()",
                )
                if cluster != same:
                    raise BackupError(
                        "Configured database and Compose source are different clusters"
                    )
                snapshot = await connection.scalar(text("SELECT pg_export_snapshot()"))
                manifest = await fingerprint(connection)
                with private_file(archive) as handle:
                    await docker(
                        "exec",
                        container,
                        "pg_dump",
                        "--format=custom",
                        "--no-owner",
                        "--no-acl",
                        "--schema=public",
                        "--snapshot=" + snapshot,
                        "--username=" + url.username,
                        "--dbname=" + url.database,
                        stdout=handle,
                    )
        digest = archive_hash(archive)
        result = {
            "created_at": datetime.now(UTC).isoformat(),
            "archive": archive.name,
            "archive_sha256": digest,
            "tables": manifest,
            "source_modified": False,
            "verified": False,
        }
        result["recovery"] = await verify_archive(
            archive,
            image,
            "lumen_restore_check",
            manifest,
            label,
            settings.daily_ai_call_cap,
        )
        result["verified"] = True
        with private_file(receipt, "x") as handle:
            handle.write(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "archive": str(archive),
                    "receipt": str(receipt),
                    "verified": True,
                    "source_modified": False,
                    "table_rows": {k: v["rows"] for k, v in manifest.items()},
                    "recovered_budget_blocked": result["recovery"][
                        "recovered_budget_blocked"
                    ],
                }
            )
        )
        return result
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "backups",
    )
    args = parser.parse_args()
    try:
        asyncio.run(backup(args))
    except (BackupError, OSError, ValueError) as error:
        raise SystemExit(
            "Backup verification failed: " + type(error).__name__
        ) from None


if __name__ == "__main__":
    main()
