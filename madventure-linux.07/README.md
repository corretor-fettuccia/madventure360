# Madventure Stitch Studio — Linux v0.7

Aplicativo experimental em Python/Tkinter para fotografias e **vídeos** dual-fisheye, com fila mista, saída panorâmica 360° e processamento local.

## O que mudou

- Interface desktop larga e redimensionável, painéis divididos e guias independentes **Calibração**, **Fotografias** e **Vídeos**.
- Importação múltipla ou de diretórios e subpastas, com detecção de extensões sem diferenciar maiúsculas/minúsculas (`.JPG`, `.jpg`, `.MP4`, `.mp4` etc.).
- Vídeo: OpenCV para decodificação quadro a quadro, projeção dual-fisheye com o motor de fotos, FFmpeg para MP4/H.264 + AAC quando existe áudio de origem. Busca manter o FPS informado pelo arquivo.
- Fila com andamento do vídeo (quadros/percentual), botão de cancelamento e opção de reunir resultados em ZIP.
- Ajuste de resolução e qualidade do vídeo em aba específica.

## Instalar e executar

No Ubuntu/Debian:

```bash
sudo apt install python3-tk python3-venv ffmpeg
cd madventure-linux
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Ou use `./executar.sh` depois de instalar as dependências.

## AppImage

`./gerar-appimage.sh` monta a aplicação usando PyInstaller e appimagetool em Linux x86_64 com internet. **O AppImage não está pré-compilado no ZIP**. O FFmpeg precisa continuar instalado na máquina (`sudo apt install ffmpeg`); o gerador atual não o incorpora.

## Limitações importantes

O algoritmo é uma **aproximação**, não uma cópia do Madventure Camera. Não utiliza parâmetros de calibração proprietários, correção de paralaxe, estabilização giroscópica nem rastreamento ótico avançado. A autocalibração angular atual é aplicada a **fotos**, não a cada quadro de vídeo; vídeos usam os parâmetros comuns definidos na aba Calibração. O áudio, quando presente, é recodificado como AAC; legendas e outras trilhas não são copiadas. Certos formatos/codec de origem podem não ser legíveis pelo OpenCV.

Vídeos 360° em resoluções grandes consomem muita RAM e CPU. Inicie testes em 1024 ou 2048 pixels. O arquivo exportado é equiretangular, mas esta versão **não incorpora metadados esféricos de reprodução 360°** específicos de YouTube e serviços semelhantes.

Testes automatizados realizados: compilação da sintaxe, aceitação de `.JPG`/`.MP4` e conversão de um vídeo MP4 sintético de 10 quadros. A aparência do programa em um desktop Linux e a qualidade com mídias reais da Madventure ainda precisam ser validadas.
