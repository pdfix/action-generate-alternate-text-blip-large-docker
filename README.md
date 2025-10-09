# Alternate Description Generator

A Docker image that automatically generates alternate description for all Figures in PDF document.

## Table of Contents

- [Alternate Description Generator](#alternate-description-generator)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
  - [Exporting Configuration for Integration](#exporting-configuration-for-integration)
  - [Model](#model)
  - [License](#license)
  - [Help \& Support](#help--support)

## Getting Started

To use this Docker application, you'll need to have Docker installed on your system. If Docker is not installed, please follow the instructions on the [official Docker website](https://docs.docker.com/get-docker/) to install it.
First run will pull the docker image, which may take some time. Make your own image for more advanced use.

## Run using Command Line Interface

To run docker container as CLI you should share the folder with PDF to process using `-v` parameter.
In this example all Figure tags without alternate description will get description of image.

```bash
docker run -v $(pwd):/data -w /data --rm pdfix/alt-text-blip-large:latest generate-alt-text -i input.pdf -o output.pdf --model /model
```

With PDFix License add these arguments.

```bash
--name ${LICENSE_NAME} --key ${LICENSE_KEY}
```

Argument `--model /model` is required in order to tell program where model is located in docker image. Without this program would fail to find model as it works in offline mode.

You can also generate alternate description just for one image using this example:

```bash
docker run -v $(pwd):/data -w /data --rm pdfix/alt-text-blip-large:latest generate-alt-text -i image.jpg -o output.txt --model /model
```

For more detailed information about the available command-line arguments, you can run the following command:

```bash
docker run --rm pdfix/alt-text-blip-large:latest --help
```

## Exporting Configuration for Integration

To export the configuration JSON file, use the following command:

```bash
docker run -v $(pwd):/data -w /data --rm pdfix/alt-text-blip-large:latest config -o config.json
```

## Model

Used model is [BLIP large](https://huggingface.co/Salesforce/blip-image-captioning-large) in offline mode (whole model is inside docker image). It is configured to work with CPU (it is slower but there is no need for high/end GPU).

## License

This repository uses the [BLIP model](https://huggingface.co/Salesforce/blip-image-captioning-large) from Salesforce, which is licensed under the [BSD 3-Clause License](https://opensource.org/licenses/BSD-3-Clause). See `THIRD_PARTY_LICENSES.md` for details.

The Docker image includes:

- PDFix SDK, subject to [PDFix Terms](https://pdfix.net/terms)
- BLIP model, BSD 3-Clause License (Salesforce)

Trial version of the PDFix SDK may apply a watermark on the page and redact random parts of the PDF including the scanned image in background. Contact us to get an evaluation or production license.

## Help & Support

To obtain a PDFix SDK license or report an issue please contact us at support@pdfix.net.
For more information visit https://pdfix.net
