export const metadata = {
  title: 'NoReply',
  description: 'Financial ledger from email ingestion',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
