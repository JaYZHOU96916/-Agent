import { NextRequest, NextResponse } from "next/server";

// This single-page workspace uses route handlers only, no Server Actions,
// image optimizer, rewrites, or client-side RSC navigation.
export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/_next/image")) return new NextResponse(null, { status: 404 });
  if (request.headers.has("next-action") || request.headers.has("rsc") || request.headers.has("next-router-state-tree"))
    return new NextResponse("Unsupported request", { status: 400 });
  if (!["GET", "HEAD"].includes(request.method) && !request.nextUrl.pathname.startsWith("/api/"))
    return new NextResponse(null, { status: 405 });
  const response = NextResponse.next();
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "same-origin");
  response.headers.set("X-Frame-Options", "DENY");
  return response;
}
export const config = { matcher: ["/((?!_next/static|favicon.ico).*)"] };
