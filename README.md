# ai-package-guard

**Problema:** IAs alucinam nomes de pacotes. Atacantes registram esses nomes e colocam malware. O desenvolvedor instala achando que é legítimo. No vibe coding com Firebase + Node isso se agrava: rules abertas, segredos no git e instalação cega por agentes.

**Solução:** Skill que força verificação antes de qualquer instalação, lockfile congelado, SBOM, checklist de segurança para Firebase/Node e gate automático.

## O que ela faz
- Rejeita pacotes inexistentes ou muito novos
- Exige confirmação humana
- `npm ci --ignore-scripts` + SBOM no CI
- Checklist de rules, segredos e testes recorrentes
- Script `security-gate.sh` + testes automatizados

## Detalhes técnicos
`verify_packages.py` consulta o registry npm e marca risco alto se o pacote não existe ou tem menos de 30 dias. O gate (`security-gate.sh`) executa `npm ci --ignore-scripts`, `npm audit`, scan de `serviceAccount`/`private_key` e checagem de `firestore.rules` com `if true`. A Action só dispara o gate quando existe `package.json`.

## Prova
- 15 casos de teste em `evals/`
- Runner gera `test-report.json` com timestamp
- GitHub Action roda em todo push
- Commits rastreáveis (ex.: security-gate `a8b547b`, workflow `a4a4595`)

## Uso rápido
```bash
git clone https://github.com/DGuedz/ai-package-guard.git
python evals/run_tests.py
bash scripts/security-gate.sh   # em projeto Node
```

Skill para Claude, Codex e agentes.  
Processo completo em `references/vibe-coding-checklist.md`.
