export default function V8Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-screen">
      {children}
    </div>
  );
}
