import "./globals.css";

export const metadata = {
  title: "图片语义检索工作台",
  description: "用于上传、搜索与相似图检索的本地工作台页面",
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
