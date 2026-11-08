# ai-package-guard

**Problema:** IAs alucinam nomes de pacotes. Atacantes registram esses nomes e colocam malware. O desenvolvedor instala achando que é legítimo. No vibe coding com Firebase + Node isso se agrava: rules abertas, segredos no git e instalação cega por agentes.

**Solução:** Skill que força verificação antes de qualquer instalação, lockfile congelado, SBOM, checklist de segurança para Firebase/Node e um gate automático.

## Ferramentas

| Script | O que faz |
|---|---|
| `scripts/verify_packages.py` | Consulta npm ou PyPI (`--ecosystem pypi`). Risco alto se o pacote não existe; médio se tem menos de 30 dias, não lista repositório ou tem nome a 1 letra de um pacote popular (typosquat). Falha de rede vira `unknown` (não verificado), nunca "não existe". |
| `scripts/lockfile_diff.py` | Compara dois `package-lock.json` (v2/v3): pacotes adicionados, removidos e alterados; sinaliza hash de integridade ausente ou trocado na mesma versão, origem fora do registry npm e scripts de instalação. |
| `scripts/security-gate.sh [dir]` | `npm ci --ignore-scripts` (exige lockfile), `npm audit` (bloqueia com `AUDIT_BLOCKING=1`), busca de credenciais reais (chave privada, service account, AWS, GitHub, Stripe, Slack) sem imprimir o valor, `.env` fora do git e regras do Firebase abertas (`if true`, `allow` sem condição, modo de teste com data, `storage.rules`, `database.rules.json`). `GATE_CHECKS="secrets env"` escolhe as checagens; `GATE_EXTRA_PATTERNS=arquivo` acrescenta padrões de segredo do projeto (uma regex por linha). |

## Prova (o que é testado e o que não é)

- `python evals/run_tests.py` executa **testes das ferramentas**: consultas reais ao npm/PyPI, typosquat, diff de lockfile e o gate rodando contra projetos de exemplo criados na hora (limpo, segredo vazado, regras abertas, sem lockfile, `.env` não ignorado). Cada projeto tem um resultado esperado; o gate anterior deixava passar 7 desses casos.
- `evals/evals.json` tem 15 **evals de comportamento** (como o agente deve responder). Eles precisam de um modelo e de um avaliador e **não são executados** pelo runner. Cada caso lista em `tool_tests` os testes que cobrem as ferramentas de que ele depende; o relatório mostra quais casos têm esse respaldo e quais são só de comportamento.
- `evals/test-report.json` registra commit, ambiente, duração e resultado de cada teste. A Action roda em todo push e PR, publica o relatório como artefato e a tabela no resumo do job.

## Uso rápido
```bash
git clone https://github.com/DGuedz/ai-package-guard.git
cd ai-package-guard
python evals/run_tests.py            # --offline pula os testes que acessam npm/PyPI
python scripts/verify_packages.py express lodash pacote-sugerido-pela-ia
bash scripts/security-gate.sh ../meu-projeto
```

Skill para Claude, Codex e agentes.
Processo completo em `references/vibe-coding-checklist.md`.
