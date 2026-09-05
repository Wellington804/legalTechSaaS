import { AIQualityLab } from "@/components/ai-quality-lab";
import { Page } from "@/components/workspace/shared";

export default function PageView() {
  return (
    <Page
      title="Qualidade da IA"
      subtitle="Teste respostas jurídicas com casos revisados antes de confiar nelas no trabalho real."
    >
      <AIQualityLab />
    </Page>
  );
}
