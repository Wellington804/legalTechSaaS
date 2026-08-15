import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { prompt, type } = await req.json();
    const apiKey = process.env.GEMINI_API_KEY || process.env.NEXT_PUBLIC_GEMINI_API_KEY;

    if (!apiKey || apiKey === "your_gemini_api_key_here") {
      return NextResponse.json(
        { error: "API Key do Gemini não configurada no servidor." },
        { status: 400 }
      );
    }

    if (type === "DESIGN") {
      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contents: [
              {
                parts: [
                  {
                    text: `Você é um designer de suporte para documentos jurídicos. Analise o conceito: "${prompt}". Retorne APENAS um JSON válido sem marcação no seguinte formato:
{"headerStyle": "SILVA_ASSOCIADOS"|"WIL_SHAFFER"|"BORDER_DOUBLE"|"SOLID"|"GRADIENT"|"MINIMAL", "headerBgColor": "#0a192f", "headerTextColor": "#ffffff", "footerStyle": "SILVA_ASSOCIADOS"|"WIL_SHAFFER"|"MINIMAL"|"SOLID"|"TWO_COLUMN", "footerBgColor": "#0a192f", "footerTextColor": "#ffffff", "docFontFamily": "serif"|"playfair"|"sans"|"outfit"|"mono", "paperBgTheme": "CREAM"|"SLATE"|"PARCHMENT"|"BLUE_SOFT"|"WHITE"|"DARK", "paperBorderFrame": "SHADOW_3D"|"GOLDEN_DOUBLE"|"MINIMAL_BORDER"|"NONE", "watermarkText": "MARCA REGISTRADA", "watermarkOpacity": 0.08}`
                  }
                ]
              }
            ]
          })
        }
      );

      if (!res.ok) {
        throw new Error(`Gemini API error: ${res.statusText}`);
      }

      const data = await res.json();
      const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || "";
      const match = text.match(/\{[\s\S]*\}/);
      if (match) {
        return NextResponse.json({ success: true, design: JSON.parse(match[0]) });
      }
      return NextResponse.json({ success: false, error: "Resposta em formato inválido." });
    }

    if (type === "DOCUMENT") {
      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contents: [
              {
                parts: [
                  {
                    text: `Você é um advogado sênior especialista em redação de petições. Redija um texto de petição formal com base no prompt: "${prompt}". Retorne apenas o texto da petição sem introduções.`
                  }
                ]
              }
            ]
          })
        }
      );

      if (!res.ok) {
        throw new Error(`Gemini API error: ${res.statusText}`);
      }

      const data = await res.json();
      const generatedText = data?.candidates?.[0]?.content?.parts?.[0]?.text || "";
      return NextResponse.json({ success: true, text: generatedText });
    }

    return NextResponse.json({ error: "Tipo de solicitação inválido." }, { status: 400 });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Erro interno ao processar requisição de IA" },
      { status: 500 }
    );
  }
}
