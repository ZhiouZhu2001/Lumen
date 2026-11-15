export default function BookCardSkeleton() {
  return <div aria-hidden="true" className="book-display book-skeleton">
    <div />
    <div className="skeleton-shape skeleton-cover" />
    <div className="skeleton-lines">
      <div className="skeleton-shape" /><div className="skeleton-shape" />
      <div className="skeleton-shape" /><div className="skeleton-shape" />
    </div>
  </div>;
}
