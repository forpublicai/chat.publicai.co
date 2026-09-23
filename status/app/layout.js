import './globals.css';

export const metadata = {
  title: 'Inference API Status',
  description: 'System Status and Service Health Dashboard',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
