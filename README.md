# Madventure Web Studio 0.2 — reconstrução independente

Aplicativo web estático, offline e sem dependências externas, criado após inspeção inicial do instalador Windows Madventure Camera 1.1.0.19 e documentação pública da família de câmeras Mi Sphere/Madventure 360.

## Executar
Abra `index.html` no Chrome/Edge/Firefox moderno. Alternativamente execute `python3 -m http.server 8080` nesta pasta e abra http://localhost:8080.

## Implementado
- Fotos e vídeos decodificados no browser, sem envio a servidores.
- Renderização WebGL para fisheye duplo horizontal ou vertical e panoramas equiretangulares existentes.
- Conversão geométrica de duas lentes para equiretangular com FOV ajustável (não equivale a calibração original).
- Navegação com mouse/toque, orientação, FOV, vista 360, plano e pequeno planeta.
- Exportação PNG de panorama completo (sujeita a limite de textura da GPU) e captura da vista.
- Reprodução e busca em vídeo, exportação da visualização como WebM (sem áudio).

## Processamento em lote
- Selecione várias imagens de uma vez ou arraste um conjunto para a área de importação.
- Clique em **Processar lote** para renderizar os panoramas PNG com os ajustes globais atuais.
- Clique em **Baixar ZIP** para obter todos os panoramas convertidos em um arquivo.
- A fila informa conclusão ou erro de cada foto; vídeos não são processados em lote nesta versão.
- Os arquivos nunca saem do navegador; memória e tamanho do ZIP dependem do dispositivo.

## Limitações técnicas
- Stitching é aproximado: não há modelo ótico calibrado do fabricante, correção de paralaxe, optical flow nem calibração individual da lente.
- Entrada automática presume vídeos/imagens com aspecto largo como fisheye lado a lado; escolha o modo correto manualmente.
- Estabilização por dados do giroscópio proprietários não implementada.
- O programa Windows não é executado aqui; a extração e decompilação dos módulos internos ainda é pendente.
- Exportação de vídeo 360° equiretangular/MP4, DNG, metadados 360 e áudio sincronizado não implementados.
- Para vídeos, o gravador WebM registra a vista atual em tempo real e sem áudio; não exporta panorama original de vídeo.

## Origem e licença
O código web é implementação nova, não contém bibliotecas, marcas gráficas nem código descompilado do produto original. Nome usado como referência funcional.

## v0.3 — Calibração automática aproximada

Novo botão **Calibrar automaticamente** ao importar foto e opção **Calibrar automaticamente ao processar lote** (ativada por padrão). O algoritmo compara amostras da área de sobreposição das lentes, busca parâmetros de campo de visão, rotação e deslocamento horizontal por minimização de diferenças fotométricas e aplica os resultados aos controles. No lote, é possível calibrar a primeira foto e reutilizar as configurações ou recalibrar individualmente cada arquivo.

**Limitações:** estimativa heurística, não é a calibração proprietária da câmera. Não recupera distorção radial complexa, centros ópticos verticais, parâmetros EXIF específicos, paralaxe ou alinhamento por correspondências de características. A automação depende de detalhes presentes na sobreposição das duas lentes. É importante conferir emendas antes de exportar um lote grande. Ainda não validada com arquivos reais Madventure.
