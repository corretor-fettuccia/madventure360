# Madventure Web Studio v0.8 — estabilidade da calibração e fila

## Correções
- Autocalibração conservadora: usa os parâmetros atuais como ponto de partida, pesquisa apenas yaw/pitch/roll até ±5° e exige pelo menos 10% de melhora na métrica para aplicar. Não altera FOV nem centro da lente automaticamente. Se a métrica não melhorar, os valores existentes permanecem.
- Amostragem de calibração preserva a razão de aspecto real da fotografia, inclusive quando as lentes estão empilhadas.
- Autocalibração automática do lote desativada por padrão; pode ser ativada manualmente.
- Após o processamento em lote, restaura os parâmetros que o operador tinha antes do lote. Os ajustes manuais são guardados no armazenamento local do navegador (quando permitido).
- Botão × para remover uma imagem ou vídeo individualmente da lista, fora do processamento. Ao modificar a fila, descarta os resultados ZIP anteriores para evitar arquivos obsoletos.
- Mantidos WebGL, 3 rotações Yaw/Pitch/Roll, e exportação JPG/JPEG/PNG/WebP com GPano MADV.

## Limitações
A métrica de autocalibração é aproximada e pode falhar com cenas sem contraste ou sobreposição insuficiente. Nesses casos, o software mantém os valores atuais. A qualidade óptica só pode ser validada contra fotografias reais e o software Madventure original.

## Execução
Abra `index.html` ou execute `python3 -m http.server 8080` dentro da pasta extraída.
