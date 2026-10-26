# Prompt de geração da documentação da reunião

> Este é um **exemplo** genérico. Ajuste à vontade: o whispering-call só lê este
> arquivo e o entrega ao Claude Code junto com a transcrição.

Você receberá a transcrição de uma reunião com timestamps no formato
`- [HH:MM:SS] texto`. A transcrição foi gerada automaticamente (Whisper) e pode
conter erros de reconhecimento, nomes grafados de forma errada e frases
truncadas. Não há identificação de quem está falando.

## Objetivo

Produzir um documento em Markdown, em português do Brasil, que permita a quem
não participou da reunião entender o que foi discutido e o que precisa ser feito.

## Estrutura do documento

1. **Título**: tema principal da reunião (inferido do conteúdo).
2. **Resumo executivo**: 3 a 6 frases.
3. **Participantes mencionados**: apenas nomes citados explicitamente; não invente.
4. **Tópicos discutidos**: uma seção por tópico, com os pontos principais e o
   timestamp de início, ex.: `(00:12:34)`.
5. **Decisões tomadas**: lista com o timestamp de onde cada decisão aparece.
6. **Itens de ação**: tabela `| Ação | Responsável | Prazo | Timestamp |`.
   Use "não definido" quando a transcrição não disser.
7. **Pendências e dúvidas em aberto**.
8. **Termos técnicos e siglas** citados, com breve explicação quando o contexto permitir.

## Regras

- Baseie-se **somente** na transcrição. Se algo for incerto, marque com
  `(incerto)` em vez de inventar.
- Corrija erros óbvios de transcrição quando o contexto deixar claro o termo
  correto; não altere o sentido do que foi dito.
- Seja objetivo: prefira listas a parágrafos longos.
- Ao terminar, salve o documento no caminho de saída informado e responda com um
  resumo de uma linha do que foi gerado.
