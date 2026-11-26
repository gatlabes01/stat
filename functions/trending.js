export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (url.pathname === "/trending") {
    return Response.redirect("https://detailz.xyz/trending/", 301);
  }
  return context.next();
}
