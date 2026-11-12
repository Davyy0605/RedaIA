# RedaIA
Plataforma de correção de redações com IA - projeto FACEPE desenvolvido em equipe na E.T.E.A.V.S 

## Transcrição por foto

Na página "Nova redação", o aluno pode enviar até 3 fotos da redação escrita à mão. A IA transcreve o texto (sem corrigir os erros do aluno) e preenche a caixa de texto para ele revisar antes de enviar. Trechos ilegíveis aparecem como `[?]`.

- Usa o mesmo `OPENAI_API_KEY`. O modelo precisa aceitar imagens: por padrão é o de `AI_MODEL`, mas dá para usar outro só para a transcrição com `AI_MODEL_TRANSCRICAO`.
- Limite por aluno: 5 transcrições por minuto e 30 por dia.
- O prompt fica em `services/prompt_transcricao.txt`.
