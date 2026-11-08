# ai-package-guard

Skill para Claude, Codex e outros agentes de IA que protege builds contra **alucinação de pacotes** (slopsquatting) e garante que você sempre confirma exatamente o que está sendo entregue.

## O que faz

- Impede instalação direta de pacotes sugeridos por IA
- Força verificação no registry (idade, repositório, maintainer)
- Exige lockfile + `npm ci --ignore-scripts` no CI
- Gera/confirma SBOM
- Inclui script de verificação em lote

## Como usar

1. Clone ou copie a pasta para o diretório de skills do seu agente:
   ```bash
   git clone https://github.com/DGuedz/ai-package-guard.git
   # ou copie a pasta para ~/.claude/skills/ ou equivalente
   ```
2. A skill ativa automaticamente quando o contexto envolve dependências, builds seguros ou pacotes sugeridos por IA.

## Script de verificação

```bash
python scripts/verify_packages.py express lodash some-package
```

## Estrutura

- `SKILL.md` — instruções principais da skill
- `scripts/verify_packages.py` — verifica pacotes no npm
- `references/` — checklist e exemplos de CI
- `evals/` — casos de teste

---

Criado para uso em ambientes Claude e Codex.
