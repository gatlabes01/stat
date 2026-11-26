export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (url.pathname === "/news") {
    return Response.redirect("https://detailz.xyz/news/", 301);
  }
  return context.next();
}
