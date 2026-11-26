# Generate Alternate Text BLIP

Runs locally and uses the BLIP large model to describe image content in alternative text. For PDF output without watermarks, a **PDFix SDK** license is required.

## Table of Contents

- [Generate Alternate Text BLIP](#generate-alternate-text-blip)
  - [Getting started](#getting-started)
  - [Usage](#usage)
  - [Commands](#commands)
  - [Arguments](#arguments)
  - [Params JSON](#params-json)
  - [How it works](#how-it-works)
  - [Exit codes](#exit-codes)
  - [Examples](#examples)
  - [Model](#model)
  - [Help \& support](#help--support)
  - [Licenses](#licenses)

## Getting started

You need Docker installed. The first run downloads the image and may take longer than later runs.

## Usage

Mount a folder into the container and run a subcommand:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/generate-alternate-text-blip-large:latest <command> [options]
```

## Commands

- `generate-alt-text`: Generate alternate text (PDF → PDF or supported image → TXT)

## Arguments

### `generate-alt-text`

| Option | Required | Type / expected value | Description |
|---|:---:|---|---|
| `--input`, `-i` | yes | Path to an existing `.pdf` or supported image file | Input PDF or image |
| `--output`, `-o` | yes | Path for output `.pdf` or `.txt` (must match mode) | Output file |
| `--model` | no | Path to model directory inside the container (default: `model`) | Local BLIP model path |
| `--params` | for PDF → PDF | Path to a `.json` file | Tag filter parameters (see [Params JSON](#params-json)) |
| `--overwrite` | no | Boolean string: `true`/`false`, `yes`/`no`, `1`/`0` (default: `false`) | Overwrite existing Alt text |
| `--zoom` | no | Float (default **2.0**) | Page render zoom for PDF mode |
| `--name` | no | String (PDFix account license name) | PDFix license name |
| `--key` | no | String (PDFix account license key) | PDFix license key |

Default tag filter when `--params` is omitted: `Figure`.

## Params JSON

`--params` points to a JSON array of parameter objects. Each object has at least `name` and `value`; the CLI reads those fields to decide which tags to process (PDF → PDF only).

### `tag_names`

`tag_names` is an ECMAScript regular expression matching tag names, or a template `tag_update` object.

Example (`example/params_alt_text.json`) — match `Figure` tags:

```json
[
    {
        "title": "Tags",
        "desc": "Specify the tags using a ECMAScript regular expression or define them by template tag_update",
        "name": "tag_names",
        "type": "tag",
        "value": "Figure",
        "values": [
            {
                "desc": "All tags",
                "value": ".*"
            }
        ]
    }
]
```

Use `"value": ".*"` to match all tags.

## How it works

- **PDF → PDF:** every tag matching `tag_names` (default `Figure`) gets a BLIP caption as alternate text (`Alt`). Without `--overwrite`, tags that already have alternate text keep it (the log shows the kept text).
- **Area of a tag:** the page and area come from the tag (its `BBox` attribute, else its content); tags without them are skipped with a warning. The area is rendered at `--zoom` into `image_<id>.jpg` in the working folder and deleted after use.
- **Blank areas:** an area of one colour gets `Blank white image`, `Blank black image` or `Blank single-color image` without calling BLIP.
- **Captions** are English, lowercase, without a final period; the BLIP artifact `arafed` is removed. The model is loaded once per run and runs offline on the CPU.
- **Image → TXT:** the caption of the image is saved in the TXT file.
- **Errors of one tag** (for example rendering) are logged, the tag is skipped and the next one is processed.
- **Checks before processing:** output extension (16) and folder (13), input (14 / 15), zoom (17), params (11 / 12), then the PDFix license.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected error (`Failed to run the program:` + traceback) |
| 10 | Invalid arguments or no command |
| 11 | Invalid regex or template in `tag_names` |
| 12 | Missing or invalid params file / parameters |
| 13 | Output folder does not exist |
| 14 | Input file is not an existing PDF |
| 15 | Input file is not an existing image (JPG, JPEG, PNG or BMP) |
| 16 | Wrong output extension (`.pdf` or `.txt`) |
| 17 | Zoom is not between 1.0 and 4.0 |
| 20–27 | PDFix SDK errors (20 initialize, 21 activate, 22 authorize, 23 render, 24 open, 25 save, 26 no tags, 27 load template); the SDK error is logged on its own line |

## Examples

Generate alternate text for figures in a PDF:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/generate-alternate-text-blip-large:latest \
  generate-alt-text --name "${LICENSE_NAME}" --key "${LICENSE_KEY}" \
  -i /data/input.pdf -o /data/output.pdf --model /model \
  --params /data/example/params_alt_text.json
```

Caption a single image to a TXT file:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/generate-alternate-text-blip-large:latest \
  generate-alt-text -i /data/image.jpg -o /data/output.txt --model /model
```

## Model

The image includes the BLIP large model and runs fully offline (CPU).

## Help & support

For PDFix SDK licensing or issues, contact `support@pdfix.net`.

## Licenses

- [PDFix Terms](https://pdfix.net/terms)
- [BLIP large model](https://huggingface.co/Salesforce/blip-image-captioning-large) — [BSD-3-Clause](https://opensource.org/licenses/BSD-3-Clause)
