export const metadata = {
  title: 'Way2Agribusiness Commodity Price Forecasting',
  description: '12-Month Operational Forecast & Uncertainty Fan Chart',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', backgroundColor: '#f8fafc', color: '#0f172a' }}>
        {children}
      </body>
    </html>
  );
}
