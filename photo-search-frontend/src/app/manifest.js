export default function manifest() {
  return {
    name: "Photo Search",
    short_name: "PhotoSearch",
    description: "用于上传、搜索与相似图检索的移动友好网页工作台",
    start_url: "/",
    display: "standalone",
    background_color: "#f5efe5",
    theme_color: "#f5efe5",
    orientation: "portrait",
    lang: "zh-CN",
    categories: ["productivity", "utilities", "photo"],
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: "/apple-icon.svg",
        sizes: "180x180",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
