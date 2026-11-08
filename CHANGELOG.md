# Changelog

## 2026-11-08 (c)
- `verify_packages.py`: até 2 novas tentativas (1 s, 2 s) em erro de rede, 429 e 5xx antes de marcar `unknown`; 404 e outros erros não repetem.

## 2026-11-08 (b)
- `security-gate.sh`: aceita diretório alvo; exige lockfile; corrige filtro `grep -v ".git"` que escondia achados (`.github`, `digit`); padrões de credenciais reais sem imprimir o valor; checa `.env` no git; cobre `allow` sem condição, modo de teste, `storage.rules` e `database.rules.json`; ignora comentários nas regras; shellcheck no CI.
- `verify_packages.py`: PyPI (`--ecosystem pypi`), nomes com escopo codificados, typosquat por distância de edição, falha de rede vira `unknown` (exit 3) em vez de "não existe".
- Novo `lockfile_diff.py` para PRs que só mudam o lockfile.
- Runner: 21 testes de ferramenta (o gate roda contra projetos de exemplo), sem registro duplicado de falha, relatório com commit/ambiente/duração e cobertura dos evals de comportamento; `tool_tests` em cada caso do `evals.json`.
- README separa o que é testado do que não é.

## 2026-11-08
- Initial skill creation
- Core workflow for Node/npm verification, lockfile + frozen installs, SBOM confirmation
- Bundled `verify_packages.py` script
- Checklist and CI examples
