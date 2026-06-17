import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Wildfire Agent Web",
  description: "위치 입력형 산불 위험 분석 및 오탐 검토 서비스",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
