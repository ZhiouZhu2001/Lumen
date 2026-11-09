import os

import pytest

from scripts.backup_database import BackupError, private_directory, private_file


def test_private_backup_files_are_exclusive_and_keep_existing_contents(tmp_path):
    folder = private_directory(tmp_path / "private")
    archive = folder / "sample.dump"
    with private_file(archive) as handle:
        handle.write(b"private test payload")
    with pytest.raises(FileExistsError), private_file(archive):
        pytest.fail("Existing backup was overwritten")
    assert archive.read_bytes() == b"private test payload"
    if os.name != "nt":
        assert folder.stat().st_mode & 0o777 == 0o700
        assert archive.stat().st_mode & 0o777 == 0o600


def test_backup_destination_rejects_unresolved_parent_traversal(tmp_path):
    path = tmp_path / ".." / "unresolved-backup"
    with pytest.raises(BackupError):
        private_directory(path)


async def test_restore_refuses_to_remove_a_populated_target_schema(
    monkeypatch, tmp_path
):
    import json

    from scripts import backup_database as module

    commands = []

    class Ready:
        async def wait(self):
            return 0

    async def process(*args, **kwargs):
        return Ready()

    async def command(*args, **kwargs):
        commands.append(args)
        if args[0] == "inspect":
            return json.dumps([{"Config": {"Labels": {"com.lumen.restore": "test"}}}])
        if args[-1] == "SELECT count(*) FROM pg_tables WHERE schemaname='public'":
            return "1"
        return ""

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", process)
    monkeypatch.setattr(module, "docker", command)
    with pytest.raises(BackupError, match="unexpectedly populated"):
        await module.verify_archive(
            tmp_path / "unused.dump", "test-image", "test_db", {}, "test", 100
        )
    assert not any("DROP SCHEMA public" in args for args in commands)
    assert any(args[:3] == ("rm", "-f", "-v") for args in commands)
