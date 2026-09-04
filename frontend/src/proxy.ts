import { NextRequest, NextResponse } from "next/server";
import { isWorkspacePath } from "./lib/navigation";

export function proxy(request: NextRequest) {
  if (isWorkspacePath(request.nextUrl.pathname)) return NextResponse.next();
  if (request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ detail: "Módulo não habilitado neste ambiente." }, { status: 404 });
  }
  return NextResponse.redirect(new URL("/dashboard", request.url));
}

export const config = {
  matcher: [
    "/dashboard/:path+",
    "/oab-hub/:path*",
    "/portal/:path*",
    "/sign/:path*",
    "/verify/:path*",
    "/api/ai/:path*",
  ],
};
