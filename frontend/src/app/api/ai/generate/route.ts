import { NextResponse } from "next/server";

// Fail closed until authenticated quotas and legal-data privacy controls are implemented.
export async function POST() {
  return NextResponse.json(
    { error: "Geração por IA não homologada. Integração indisponível até validação de autenticação, quotas e privacidade." },
    { status: 503 }
  );
}
