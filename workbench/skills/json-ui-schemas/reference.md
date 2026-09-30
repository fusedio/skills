# JSON UI component schemas

## ai-chat

AI chat for connected UDFs.

~~~json
{
  "type": "object",
  "properties": {
    "title": {
      "description": "Optional title displayed beside the chat surface",
      "type": "string"
    },
    "description": {
      "description": "Optional helper text displayed beside the chat surface",
      "type": "string"
    },
    "systemPromptExtra": {
      "description": "Optional additional system prompt appended to the AI chat instructions",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"height: 500px; border-radius: 8px\")",
      "type": "string"
    }
  },
  "description": "Always-on AI chat for asking questions about UDFs connected to this JSON UI node.\n\n## Example\n\n```json\n{\n  \"type\": \"ai-chat\",\n  \"props\": {\n    \"title\": \"Ask about this data\"\n  }\n}\n```"
}
~~~

## bar-chart

Bar chart driven by DuckDB SQL query.

~~~json
{
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'label' and 'value' columns."
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "barColor": {
      "default": "#E8FF59",
      "description": "Bar fill color. Default is Fused lime yellow (#E8FF59).",
      "type": "string"
    },
    "barOpacity": {
      "default": 1,
      "description": "Bar fill opacity from 0 (transparent) to 1 (solid).",
      "type": "number"
    },
    "barRadius": {
      "default": 4,
      "description": "Corner radius of bars in pixels. 0 for sharp corners.",
      "type": "number"
    },
    "hoverColor": {
      "description": "Bar fill color on hover. If omitted, no hover highlight is shown.",
      "type": "string"
    },
    "showGrid": {
      "default": false,
      "description": "Show subtle horizontal grid lines behind bars.",
      "type": "boolean"
    },
    "rotateLabels": {
      "default": true,
      "description": "Rotate x-axis labels -45 degrees. Useful for long category names.",
      "type": "boolean"
    },
    "horizontal": {
      "default": false,
      "description": "If true, renders horizontal bars (categories on y-axis, values on x-axis). Good for ranked lists.",
      "type": "boolean"
    },
    "showValues": {
      "default": false,
      "description": "Show the numeric value label on each bar.",
      "type": "boolean"
    },
    "xAxisFontSize": {
      "default": 11,
      "description": "Font size for x-axis labels in pixels.",
      "type": "number"
    },
    "yAxisFontSize": {
      "default": 11,
      "description": "Font size for y-axis labels in pixels.",
      "type": "number"
    },
    "bottomMargin": {
      "description": "Bottom margin in pixels. Overrides the auto-calculated value from rotateLabels. Useful when labels are clipped.",
      "type": "number"
    },
    "beginAtZero": {
      "default": true,
      "description": "Force the value axis to start at 0.",
      "type": "boolean"
    },
    "animationMs": {
      "default": 300,
      "description": "Bar animation duration in milliseconds. 0 disables animation. Default 300ms, and animation only runs when data changes.",
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"padding: 8px; background-color: #1a1a1a\")",
      "type": "string"
    }
  },
  "required": [
    "sql"
  ],
  "description": "A bar chart powered by DuckDB SQL queries against UDF outputs. Query must return 'label' and 'value' columns. Uses {{udf_name}} placeholders to reference UDF DataFrames.\n\n## Example\n\n```json\n{\n  \"type\": \"bar-chart\",\n  \"props\": {\n    \"sql\": \"SELECT neighborhood AS label, COUNT(*) AS value FROM {{listings}} GROUP BY 1 ORDER BY 2 DESC LIMIT 10\",\n    \"title\": \"Listings by Neighborhood\"\n  }\n}\n```\n\n## Example \u2014 horizontal\n\n```json\n{\n  \"type\": \"bar-chart\",\n  \"props\": {\n    \"sql\": \"SELECT city AS label, population AS value FROM {{cities}} ORDER BY 2 DESC\",\n    \"horizontal\": true,\n    \"showValues\": true\n  }\n}\n```"
}
~~~

## button

Clickable button with optional param broadcast.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "default": "Button",
      "type": "string"
    },
    "variant": {
      "default": "default",
      "type": "string",
      "enum": [
        "default",
        "destructive",
        "outline",
        "secondary",
        "ghost",
        "link"
      ]
    },
    "size": {
      "default": "default",
      "type": "string",
      "enum": [
        "default",
        "sm",
        "lg"
      ]
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "param": {
      "description": "Canvas parameter name to sync click count with. Each click increments the count.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    },
    "centered": {
      "default": false,
      "description": "If true, centers the button within the node.",
      "type": "boolean"
    }
  },
  "description": "A clickable button for triggering actions. If `param` is provided, broadcasts a click signal to that canvas parameter.\n\n## Example\n\n```json\n{\n  \"type\": \"button\",\n  \"props\": {\n    \"label\": \"Submit\",\n    \"variant\": \"default\",\n    \"param\": \"submit_count\"\n  }\n}\n```"
}
~~~

## camera-input

Camera input that stores captured photos as data URLs.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the camera input",
      "type": "string"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. Captured images are stored as data URL strings.",
      "type": "string"
    },
    "defaultValue": {
      "default": "",
      "type": "string"
    },
    "facingMode": {
      "default": "environment",
      "type": "string",
      "enum": [
        "user",
        "environment"
      ]
    },
    "imageFormat": {
      "default": "jpeg",
      "type": "string",
      "enum": [
        "png",
        "jpeg",
        "webp"
      ]
    },
    "quality": {
      "default": 0.92,
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "readOnly": {
      "default": false,
      "type": "boolean"
    },
    "startLabel": {
      "default": "Start camera",
      "type": "string"
    },
    "buttonLabel": {
      "default": "Capture photo",
      "type": "string"
    },
    "sendPhotoLabel": {
      "default": "Send photo",
      "type": "string"
    },
    "retakeLabel": {
      "default": "Retake",
      "type": "string"
    },
    "clearLabel": {
      "default": "Clear",
      "type": "string"
    },
    "errorMessage": {
      "default": "Could not access camera.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "description": "A camera input that captures a photo as a data URL string and can optionally sync with canvas parameters or a form.\n\n## Example\n\n```json\n{\n  \"type\": \"camera-input\",\n  \"props\": {\n    \"label\": \"Photo\",\n    \"param\": \"photo_data_url\",\n    \"facingMode\": \"environment\"\n  }\n}\n```"
}
~~~

## code-editor

Code editor with syntax highlighting.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label displayed above the editor",
      "type": "string"
    },
    "param": {
      "description": "Canvas parameter name to sync the editor content with",
      "type": "string"
    },
    "defaultValue": {
      "default": "",
      "description": "Initial content",
      "type": "string"
    },
    "language": {
      "default": "sql",
      "description": "Syntax highlighting language.",
      "type": "string",
      "enum": [
        "sql",
        "python",
        "javascript",
        "json",
        "markdown"
      ]
    },
    "placeholderText": {
      "default": "Enter code...",
      "type": "string"
    },
    "readOnly": {
      "default": false,
      "type": "boolean"
    },
    "debounceMs": {
      "default": 0,
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles (e.g. \"padding: 8px\")",
      "type": "string"
    }
  },
  "description": "Code editor with multi-language syntax highlighting. Syncs content with a canvas parameter.\n\n## Example \u2014 SQL\n\n```json\n{\n  \"type\": \"code-editor\",\n  \"props\": {\n    \"param\": \"my_query\",\n    \"language\": \"sql\",\n    \"defaultValue\": \"SELECT * FROM {{my_udf}} LIMIT 10\"\n  }\n}\n```\n\n## Example \u2014 Python\n\n```json\n{\n  \"type\": \"code-editor\",\n  \"props\": {\n    \"param\": \"code\",\n    \"language\": \"python\",\n    \"defaultValue\": \"import pandas as pd\"\n  }\n}\n```"
}
~~~

## color-input

Color input with optional param sync.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the color input",
      "type": "string"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular color input.",
      "type": "string"
    },
    "defaultValue": {
      "default": "#000000",
      "type": "string"
    },
    "format": {
      "default": "hex",
      "description": "Output color format stored in the synced value.",
      "type": "string",
      "enum": [
        "hex",
        "rgb",
        "hsl",
        "hsb"
      ]
    },
    "showAlpha": {
      "default": false,
      "type": "boolean"
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "readOnly": {
      "default": false,
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "description": "A color input that can optionally sync string color values with canvas parameters. Hex strings are recommended for chart and CSS interoperability.\n\n## Example\n\n```json\n{\n  \"type\": \"color-input\",\n  \"props\": {\n    \"label\": \"Highlight color\",\n    \"param\": \"highlight_color\",\n    \"defaultValue\": \"#2563eb\"\n  }\n}\n```"
}
~~~

## datetime-input

Date, time, or datetime input with optional param sync.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the datetime input",
      "type": "string"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular datetime input.",
      "type": "string"
    },
    "mode": {
      "default": "date",
      "description": "Input mode. Use date for YYYY-MM-DD, time for HH:mm, or datetime for YYYY-MM-DDTHH:mm.",
      "type": "string",
      "enum": [
        "date",
        "time",
        "datetime"
      ]
    },
    "defaultValue": {
      "default": "",
      "type": "string"
    },
    "min": {
      "type": "string"
    },
    "max": {
      "type": "string"
    },
    "step": {
      "type": "number",
      "exclusiveMinimum": 0
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "readOnly": {
      "default": false,
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "description": "A date, time, or local datetime input that can optionally sync string values with canvas parameters. Values are stored without timezone conversion.\n\n## Example\n\n```json\n{\n  \"type\": \"datetime-input\",\n  \"props\": {\n    \"label\": \"Start date\",\n    \"param\": \"start_date\",\n    \"mode\": \"date\",\n    \"defaultValue\": \"2026-01-01\"\n  }\n}\n```"
}
~~~

## div

Container for grouping child elements.

~~~json
{
  "type": "object",
  "properties": {
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"display: flex; gap: 8px; padding: 16px\")",
      "type": "string"
    }
  },
  "description": "A generic container for grouping elements. Can contain any child components. Defaults to a flex column.\n\n## Example\n\n```json\n{\n  \"type\": \"div\",\n  \"props\": { \"style\": \"display: flex; gap: 8px; padding: 16px\" },\n  \"children\": [\n    { \"type\": \"text-input\", \"props\": { \"label\": \"Name\", \"param\": \"name\" } },\n    { \"type\": \"button\", \"props\": { \"label\": \"Submit\", \"param\": \"submit\" } }\n  ]\n}\n```"
}
~~~

## donut-chart

Donut chart driven by DuckDB SQL query.

~~~json
{
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'label' and 'value' columns."
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "innerRadius": {
      "default": 56,
      "description": "Inner radius in pixels (donut hole size).",
      "type": "number"
    },
    "outerRadius": {
      "default": 88,
      "description": "Outer radius in pixels.",
      "type": "number"
    },
    "showLegend": {
      "default": true,
      "description": "Show category legend.",
      "type": "boolean"
    },
    "showLabels": {
      "default": false,
      "description": "Show percentage labels on slices.",
      "type": "boolean"
    },
    "showCenterTotal": {
      "default": true,
      "description": "Show total value text in donut center.",
      "type": "boolean"
    },
    "animationMs": {
      "default": 300,
      "description": "Animation duration in milliseconds. 0 disables animation. Animation only plays on data changes, not on zoom/resize.",
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string.",
      "type": "string"
    }
  },
  "required": [
    "sql"
  ],
  "description": "A donut chart powered by DuckDB SQL. Query must return label and value columns.\n\n## Example\n\n```json\n{\n  \"type\": \"donut-chart\",\n  \"props\": {\n    \"sql\": \"SELECT room_type AS label, COUNT(*) AS value FROM {{listings}} GROUP BY 1\",\n    \"title\": \"Listings by Room Type\"\n  }\n}\n```"
}
~~~

## dropdown

Select dropdown with SQL or static options.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the dropdown",
      "type": "string"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular dropdown.",
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'value' and 'label' columns. Takes precedence over options. Requires at least one {{udf_name}} placeholder.",
      "type": "string"
    },
    "options": {
      "description": "Static array of options. Used when sql is not provided or when sql fails. Each option must have non-empty value and label.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "value": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "object",
                "propertyNames": {
                  "type": "string"
                },
                "additionalProperties": {}
              }
            ]
          },
          "label": {
            "type": "string"
          }
        },
        "required": [
          "value"
        ],
        "description": "A single dropdown option with value (string or object) and label (displayed). String options with empty value are filtered out."
      }
    },
    "placeholder": {
      "default": "Select an option...",
      "description": "Placeholder text shown when nothing is selected",
      "type": "string"
    },
    "defaultValue": {
      "default": "",
      "description": "Initial value when no canvas/form value exists. Can be a constant string, UDF query (e.g., {{my_udf.default_city[0]}}), or a JSON object matching an option value.",
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "object",
          "propertyNames": {
            "type": "string"
          },
          "additionalProperties": {}
        }
      ]
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    },
    "centered": {
      "default": false,
      "description": "If true, centers the dropdown within the node.",
      "type": "boolean"
    },
    "nullable": {
      "default": false,
      "description": "If true, the dropdown does not auto-select the first option when no defaultValue is provided. The param starts cleared/null.",
      "type": "boolean"
    },
    "allowInvalidValue": {
      "default": false,
      "description": "If true, preserves param values that are not present in the current options. If false, clears invalid param values.",
      "type": "boolean"
    },
    "searchable": {
      "default": false,
      "description": "If true, shows a search input inside the dropdown panel.",
      "type": "boolean"
    }
  },
  "description": "A dropdown that syncs with canvas parameters. Prefer `sql` (a DuckDB query with `{{udf_name}}` placeholders returning `value` and `label` columns) for dynamic options from UDF DataFrames. Fall back to the `options` array for static choices.\n\n## Example \u2014 SQL (dynamic)\n\n```json\n{\n  \"type\": \"dropdown\",\n  \"props\": {\n    \"label\": \"Select City\",\n    \"param\": \"city\",\n    \"sql\": \"SELECT DISTINCT city AS value, city AS label FROM {{my_udf}} ORDER BY city\"\n  }\n}\n```\n\n## Example \u2014 static options\n\n```json\n{\n  \"type\": \"dropdown\",\n  \"props\": {\n    \"label\": \"Select Country\",\n    \"param\": \"country\",\n    \"options\": [\n      { \"value\": \"us\", \"label\": \"United States\" },\n      { \"value\": \"uk\", \"label\": \"United Kingdom\" }\n    ]\n  }\n}\n```"
}
~~~

## file-upload

Upload files to S3/fd/gs from a browser picker or param content.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the file upload widget",
      "type": "string"
    },
    "destinationPath": {
      "type": "string",
      "description": "Destination storage path (s3://, fd://, or gs://). Supports $param substitution."
    },
    "sourceMode": {
      "default": "picker",
      "description": "Source for files: picker (browser file picker) or content (param with base64 JSON).",
      "type": "string",
      "enum": [
        "picker",
        "content"
      ]
    },
    "contentParam": {
      "description": "Canvas parameter containing file content as JSON: [{ name, content (base64), contentType? }] or a single object.",
      "type": "string"
    },
    "param": {
      "description": "Optional output parameter. On success, broadcasts a JSON array of { path, fileName } objects.",
      "type": "string"
    },
    "autoUpload": {
      "description": "When true, uploads automatically once the source is ready. Defaults to false for picker and true for content mode.",
      "type": "boolean"
    },
    "uploadLabel": {
      "default": "Upload",
      "type": "string"
    },
    "accept": {
      "description": "Optional accept attribute for the browser file picker.",
      "type": "string"
    },
    "multiple": {
      "default": true,
      "description": "Allow selecting multiple files in picker mode.",
      "type": "boolean"
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "readOnly": {
      "default": false,
      "description": "If true, blocks local interactions.",
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "required": [
    "destinationPath"
  ],
  "description": "Uploads files to a configured storage destination after validating write access for the current user token."
}
~~~

## form

Form container that submits child values together.

~~~json
{
  "type": "object",
  "properties": {
    "param": {
      "description": "Optional canvas parameter name to broadcast consolidated form data to. If omitted, each child field is broadcast individually on submit.",
      "type": "string"
    },
    "submitLabel": {
      "default": "Submit",
      "type": "string"
    },
    "submitPosition": {
      "default": "bottom",
      "description": "Position of the submit button",
      "type": "string",
      "enum": [
        "bottom",
        "top"
      ]
    },
    "card": {
      "default": true,
      "description": "If true, wraps the form in a card-like container.",
      "type": "boolean"
    },
    "centered": {
      "default": false,
      "description": "If true, centers the form container within the node.",
      "type": "boolean"
    },
    "title": {
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"padding: 16px; background-color: #f0f0f0\")",
      "type": "string"
    }
  },
  "description": "A form container that collects child input values and submits them on button click. If `param` is provided, all child values are broadcast as one JSON object to that parameter. If omitted, each child field is broadcast individually. Children use their own `param` prop to register with the form. Supported child types: text-input, text-area, number-input, datetime-input, camera-input, color-input, dropdown, slider, and text.\n\n## Example\n\n```json\n{\n  \"type\": \"form\",\n  \"props\": {\n    \"param\": \"form_data\",\n    \"submitLabel\": \"Submit\"\n  },\n  \"children\": [\n    { \"type\": \"text-input\", \"props\": { \"label\": \"Name\", \"param\": \"user_name\" } },\n    {\n      \"type\": \"dropdown\",\n      \"props\": {\n        \"label\": \"City\",\n        \"param\": \"city\",\n        \"sql\": \"SELECT DISTINCT city AS value, city AS label FROM {{my_udf}} ORDER BY city\"\n      }\n    }\n  ]\n}\n```"
}
~~~

## fused-map

Interactive map with tile and vector layers.

~~~json
{
  "type": "object",
  "properties": {
    "basemap": {
      "default": "mapbox://styles/mapbox/dark-v11",
      "description": "Mapbox style URL",
      "type": "string"
    },
    "centerLng": {
      "default": -98,
      "type": "number"
    },
    "centerLat": {
      "default": 39.5,
      "type": "number"
    },
    "zoom": {
      "default": 4,
      "type": "number"
    },
    "minZoom": {
      "description": "Minimum zoom level (0-24)",
      "type": "number"
    },
    "maxZoom": {
      "description": "Maximum zoom level (0-24)",
      "type": "number"
    },
    "layers": {
      "default": [],
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string",
            "description": "Unique layer identifier"
          },
          "name": {
            "description": "Display name for the layer",
            "type": "string"
          },
          "type": {
            "type": "string",
            "enum": [
              "mvt",
              "raster",
              "geojson",
              "h3",
              "heatmap",
              "arc",
              "scatterplot",
              "deck-geojson"
            ],
            "description": "Layer type: mvt/raster/geojson (Mapbox native), h3/heatmap/arc/scatterplot/deck-geojson (deck.gl)"
          },
          "visible": {
            "default": true,
            "type": "boolean"
          },
          "tileUrl": {
            "description": "Tile URL template with {x}/{y}/{z} placeholders (mvt, raster, tiled h3)",
            "type": "string"
          },
          "minZoom": {
            "description": "Minimum zoom for tiled layers (mvt, raster, tiled h3)",
            "type": "number"
          },
          "maxZoom": {
            "description": "Maximum zoom for tiled layers (mvt, raster, tiled h3)",
            "type": "number"
          },
          "zoomOffset": {
            "description": "Zoom offset for tiled layers (useful for hex tile generalization)",
            "type": "number"
          },
          "maxRequests": {
            "description": "Maximum parallel tile requests for tiled layers",
            "type": "number"
          },
          "sourceLayer": {
            "description": "Source layer name for MVT tiles (defaults to 'default')",
            "type": "string"
          },
          "data": {
            "description": "Inline GeoJSON FeatureCollection (geojson type)"
          },
          "sql": {
            "description": "DuckDB SQL query with {{udf_name}} placeholders. Rows are converted to GeoJSON for rendering.",
            "type": "string"
          },
          "geometryColumn": {
            "description": "Column containing GeoJSON geometry strings (use ST_AsGeoJSON in SQL). Defaults to 'geometry'.",
            "type": "string"
          },
          "h3Column": {
            "description": "Column containing H3 hex indexes (for h3 layer type).",
            "type": "string"
          },
          "latColumn": {
            "description": "Column for latitude (point data). Defaults to 'lat'.",
            "type": "string"
          },
          "lngColumn": {
            "description": "Column for longitude (point data). Defaults to 'lng'.",
            "type": "string"
          },
          "tooltip": {
            "description": "Show tooltip on hover. true = all properties, string[] = specific properties.",
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "array",
                "items": {
                  "type": "string"
                }
              }
            ]
          },
          "legend": {
            "description": "Show color legend for this layer. true = auto title, {title} = custom title. Only applies when fillColor or lineColor is data-driven.",
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "object",
                "properties": {
                  "title": {
                    "type": "string"
                  }
                }
              }
            ]
          },
          "style": {
            "type": "object",
            "properties": {
              "fillColor": {
                "description": "Fill color: [r,g,b], CSS string, or data-driven {type:\"continuous\"|\"categorical\", attr, ...}"
              },
              "lineColor": {
                "description": "Stroke color: [r,g,b], CSS string, or data-driven {type:\"continuous\"|\"categorical\", attr, ...}"
              },
              "lineWidth": {
                "description": "Stroke width in pixels",
                "type": "number"
              },
              "opacity": {
                "description": "Layer opacity 0-1",
                "type": "number",
                "minimum": 0,
                "maximum": 1
              },
              "pointRadius": {
                "description": "Circle radius for point features",
                "type": "number"
              },
              "coverage": {
                "description": "H3 hex coverage 0-1 (1 = no gap, 0.8 = small gaps)",
                "type": "number",
                "minimum": 0,
                "maximum": 1
              },
              "extruded": {
                "description": "Enable 3D extrusion (h3, deck-geojson)",
                "type": "boolean"
              },
              "elevationAttr": {
                "description": "Feature property to use for extrusion height",
                "type": "string"
              },
              "elevationScale": {
                "description": "Multiplier for extrusion height values",
                "type": "number"
              }
            }
          }
        },
        "required": [
          "id",
          "type"
        ]
      }
    },
    "showControls": {
      "default": true,
      "description": "Show zoom navigation controls",
      "type": "boolean"
    },
    "showScale": {
      "default": true,
      "description": "Show scale bar",
      "type": "boolean"
    },
    "showBasemapSwitcher": {
      "default": true,
      "description": "Show dark/light/satellite basemap toggle",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show color legend for layers with data-driven colors",
      "type": "boolean"
    },
    "showLayerPanel": {
      "default": true,
      "description": "Show layer controls panel for toggling visibility and opacity",
      "type": "boolean"
    },
    "param": {
      "description": "Canvas parameter name to sync viewport bounds [west, south, east, north]",
      "type": "string"
    },
    "autoSend": {
      "default": false,
      "description": "Automatically send bounds on pan/zoom",
      "type": "boolean"
    },
    "autoSendDebounceMs": {
      "default": 600,
      "description": "Debounce ms for auto-send (0 = send on every move)",
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string",
      "type": "string"
    }
  },
  "description": "Interactive map with Mapbox GL (mvt, raster, geojson) and deck.gl (h3, heatmap, arc, scatterplot) layers.\n\n## Example \u2014 MVT tile layer\n\n```json\n{\n  \"type\": \"fused-map\",\n  \"props\": {\n    \"layers\": [{\n      \"id\": \"counties\",\n      \"type\": \"mvt\",\n      \"tileUrl\": \"https://tiles.fused.io/public/my_tileset/{z}/{x}/{y}\",\n      \"style\": { \"fillColor\": [100, 150, 200], \"opacity\": 0.6 }\n    }]\n  }\n}\n```\n\n## Example \u2014 SQL with lat/lng points\n\n```json\n{\n  \"type\": \"fused-map\",\n  \"props\": {\n    \"layers\": [{\n      \"id\": \"sites\",\n      \"type\": \"geojson\",\n      \"sql\": \"SELECT name, lat, lng FROM {{my_udf}}\",\n      \"style\": { \"fillColor\": [255, 80, 0], \"pointRadius\": 8 }\n    }]\n  }\n}\n```\n\n## Example \u2014 raster tile layer\n\n```json\n{\n  \"type\": \"fused-map\",\n  \"props\": {\n    \"layers\": [{\n      \"id\": \"seismic\",\n      \"type\": \"raster\",\n      \"tileUrl\": \"https://udf.ai/<token>/run/tiles/{z}/{x}/{y}?format=png\",\n      \"style\": { \"opacity\": 0.8 }\n    }]\n  }\n}\n```\n\nRaster layers render through a Mapbox raster source, so `tileUrl` must be a publicly fetchable XYZ endpoint (a Fused UDF tile endpoint or any external raster service); only `opacity` and `visible` apply."
}
~~~

## gallery-input

Image-card gallery input with horizontal, vertical, or grid layout and SQL or static options.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the gallery",
      "type": "string"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular gallery input.",
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return value, title, and image columns. Takes precedence over options. Requires at least one {{udf_name}} placeholder.",
      "type": "string"
    },
    "options": {
      "description": "Static array of options. Used when sql is not provided or when sql fails. Each option must have value, title, and image.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "value": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "object",
                "propertyNames": {
                  "type": "string"
                },
                "additionalProperties": {}
              }
            ]
          },
          "title": {
            "type": "string",
            "description": "Title displayed under the image"
          },
          "image": {
            "type": "string",
            "description": "Image URL or base64 data URL"
          }
        },
        "required": [
          "value",
          "title",
          "image"
        ],
        "description": "A single gallery option with value, title, and image. String options with empty value are filtered out."
      }
    },
    "defaultValue": {
      "default": "",
      "description": "Initial value when no canvas/form value exists. Can be a constant string, UDF query (e.g., {{my_udf.default_id[0]}}), or a JSON object matching an option value.",
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "object",
          "propertyNames": {
            "type": "string"
          },
          "additionalProperties": {}
        }
      ]
    },
    "mode": {
      "default": "horizontal",
      "description": "Layout mode. Use horizontal for a horizontal scroll row, vertical for a vertical scroll column, or grid for a non-scrollable wrapping layout. Legacy values carousel and vertical-carousel are still supported.",
      "type": "string",
      "enum": [
        "horizontal",
        "vertical",
        "grid",
        "carousel",
        "vertical-carousel"
      ]
    },
    "nullable": {
      "default": false,
      "description": "If true, the gallery does not auto-select the first option when no defaultValue is provided. The param starts cleared/null.",
      "type": "boolean"
    },
    "cardHeight": {
      "default": 200,
      "description": "Card height in pixels.",
      "type": "number",
      "exclusiveMinimum": 0
    },
    "cardWidth": {
      "default": 280,
      "description": "Card width in pixels.",
      "type": "number",
      "exclusiveMinimum": 0
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"padding: 8px; max-width: 640px\")",
      "type": "string"
    }
  },
  "description": "An image-card gallery input with horizontal, vertical, or grid layout that syncs with canvas parameters. Prefer sql (DuckDB query with {{udf_name}} placeholders returning value, title, and image columns) for dynamic options from UDF DataFrames. Fall back to options array for static choices.\n\n## Example \u2014 SQL\n\n```json\n{\n  \"type\": \"gallery-input\",\n  \"props\": {\n    \"label\": \"Select a dataset\",\n    \"param\": \"dataset\",\n    \"sql\": \"SELECT id AS value, name AS title, thumbnail AS image FROM {{datasets}}\"\n  }\n}\n```\n\n## Example \u2014 static options\n\n```json\n{\n  \"type\": \"gallery-input\",\n  \"props\": {\n    \"label\": \"Select style\",\n    \"param\": \"map_style\",\n    \"options\": [\n      { \"value\": \"dark\", \"title\": \"Dark\", \"image\": \"https://example.com/dark.png\" },\n      { \"value\": \"light\", \"title\": \"Light\", \"image\": \"https://example.com/light.png\" }\n    ]\n  }\n}\n```"
}
~~~

## heatmap-chart

Heatmap chart driven by DuckDB SQL query.

~~~json
{
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'x', 'y', and 'value' columns."
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "showValues": {
      "default": false,
      "description": "Show numeric values inside each cell.",
      "type": "boolean"
    },
    "cellGap": {
      "default": 4,
      "description": "Gap between heatmap cells in pixels.",
      "type": "number"
    },
    "minCellHeight": {
      "default": 28,
      "description": "Minimum cell height in pixels.",
      "type": "number"
    },
    "lowColor": {
      "default": "#111827",
      "description": "Color for the minimum value.",
      "type": "string"
    },
    "highColor": {
      "default": "#E8FF59",
      "description": "Color for the maximum value.",
      "type": "string"
    },
    "xLabel": {
      "description": "Optional x-axis title.",
      "type": "string"
    },
    "yLabel": {
      "description": "Optional y-axis title.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string.",
      "type": "string"
    }
  },
  "required": [
    "sql"
  ],
  "description": "A matrix heatmap powered by DuckDB SQL. Query must return x, y, and value columns.\n\n## Example\n\n```json\n{\n  \"type\": \"heatmap-chart\",\n  \"props\": {\n    \"sql\": \"SELECT day_of_week AS x, hour AS y, COUNT(*) AS value FROM {{events}} GROUP BY 1, 2\",\n    \"title\": \"Events by Day and Hour\"\n  }\n}\n```"
}
~~~

## html

Sandboxed HTML renderer with $param and {{udf}} substitution and window.fused API. (The bundled CLI schema text still says `fusedCanvas`; that API was removed — see the `workbench:html-template-nodes` skill for the `window.fused` contract.)

~~~json
{
  "type": "object",
  "properties": {
    "value": {
      "default": "",
      "description": "Raw HTML value. Supports $param_name placeholders for dynamic values and {{udf_name}} to inline HTML template or stringified UDF output.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles for the container (e.g., \"min-height: 200px\")",
      "type": "string"
    }
  },
  "description": "Sandboxed HTML with $param_name and {{udf_name}} substitution. Exposes window.fused: fused.env (\"workbench\"); fused.params.get(name) / .getAll() / .set(name, value) / .set({...}) / .set(name, null) to clear / .onChange(cb), backed by canvas params so connected nodes and $param placeholders react; and await fused.runPython(udfName, params) to run a connected canvas UDF and get its JSON result.\n\n## Example\n\n```json\n{\n  \"type\": \"html\",\n  \"props\": {\n    \"value\": \"<h2>Hello, $user_name!</h2><p>Selected city: <b>$city</b></p>\"\n  }\n}\n```"
}
~~~

## iframe

Embed a web page or HTML-returning UDF in an iframe using http(s) URLs, $param URL templates, or {{udf}} placeholders.

~~~json
{
  "type": "object",
  "properties": {
    "src": {
      "type": "string",
      "description": "Absolute http or https URL, optionally with $param references, or an exact UDF placeholder like {{udf}} or {{udf?name=$param}}."
    },
    "title": {
      "description": "Accessible title for the embedded content",
      "type": "string"
    },
    "allow": {
      "description": "Optional allow attribute (e.g. camera; microphone; geolocation)",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"border-radius: 8px\")",
      "type": "string"
    }
  },
  "required": [
    "src"
  ],
  "description": "Embeds a web page or HTML-returning UDF in an iframe. Use for dashboards, docs, or any site that permits framing.\n\n## Example\n\n```json\n{\n  \"type\": \"iframe\",\n  \"props\": {\n    \"src\": \"https://docs.fused.io\",\n    \"title\": \"Fused documentation\",\n    \"style\": \"border-radius: 8px; height: 500px\"\n  }\n}\n```"
}
~~~

## image

Display an image from a URL, base64 data URL, or signable storage path.

~~~json
{
  "type": "object",
  "properties": {
    "src": {
      "type": "string",
      "description": "Image URL, base64 data URL, or signable storage path (e.g., \"s3://bucket/image.png\")"
    },
    "alt": {
      "description": "Accessible description of the image",
      "type": "string"
    },
    "objectFit": {
      "default": "contain",
      "description": "How the image fits its container",
      "type": "string",
      "enum": [
        "contain",
        "cover",
        "fill",
        "none",
        "scale-down"
      ]
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"opacity: 0.8; border-radius: 8px\")",
      "type": "string"
    }
  },
  "required": [
    "src"
  ],
  "description": "Displays an image from a URL, base64 data URL, or signable storage path. Useful for showing pasted images, charts, or any visual asset.\n\n## Example\n\n```json\n{\n  \"type\": \"image\",\n  \"props\": {\n    \"src\": \"https://example.com/map.png\",\n    \"alt\": \"Map preview\",\n    \"objectFit\": \"contain\"\n  }\n}\n```"
}
~~~

## kepler-map

Embed the Kepler.gl viewer for a workspace UDF. Use {{udf_1}} to bind the connected UDF via a slot, or supply a plain UDF name as a fallback.

~~~json
{
  "type": "object",
  "properties": {
    "udf": {
      "type": "string",
      "minLength": 1,
      "description": "UDF slot placeholder (e.g. {{udf_1}}) or plain UDF name whose results should be displayed in Kepler.gl."
    },
    "title": {
      "description": "Accessible title for the embedded Kepler.gl map",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"min-height: 480px; border-radius: 8px\")",
      "type": "string"
    }
  },
  "required": [
    "udf"
  ],
  "description": "Embeds the Kepler.gl viewer for a UDF in the workspace. Accepts a {{udf_N}} slot placeholder or a plain UDF name. Uses a parquet share URL when the canvas is shared; falls back to a temporary GeoJSON upload otherwise.\n\n## Example\n\n```json\n{\n  \"type\": \"kepler-map\",\n  \"props\": {\n    \"udf\": \"{{my_udf}}\",\n    \"title\": \"My Kepler Map\",\n    \"style\": \"min-height: 480px; border-radius: 8px;\"\n  }\n}\n```"
}
~~~

## line-chart

Line/area chart for time series driven by DuckDB SQL query.

~~~json
{
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'label' and 'value' columns. Optional 'series' column for multi-line charts."
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "lineColor": {
      "default": "#E8FF59",
      "description": "Line color for single-series charts. Ignored when multiple series are present (auto-palette is used). Default is Fused lime yellow (#E8FF59).",
      "type": "string"
    },
    "lineWidth": {
      "default": 2,
      "description": "Line stroke width in pixels.",
      "type": "number"
    },
    "lineOpacity": {
      "default": 1,
      "description": "Line stroke opacity from 0 (transparent) to 1 (solid).",
      "type": "number"
    },
    "showDots": {
      "default": false,
      "description": "Show data point dots on the line.",
      "type": "boolean"
    },
    "dotSize": {
      "default": 3,
      "description": "Radius of data point dots in pixels.",
      "type": "number"
    },
    "activeDotSize": {
      "default": 5,
      "description": "Radius of the active (hovered) data point dot in pixels.",
      "type": "number"
    },
    "showArea": {
      "default": true,
      "description": "Fill the area under the line with a gradient.",
      "type": "boolean"
    },
    "areaOpacity": {
      "default": 0.2,
      "description": "Opacity of the area fill (0-1). Only used when showArea is true.",
      "type": "number"
    },
    "curveType": {
      "default": "smooth",
      "description": "Interpolation curve: \"linear\" for straight segments, \"smooth\" for bezier curves, \"step\" for stepped lines.",
      "type": "string",
      "enum": [
        "linear",
        "smooth",
        "step"
      ]
    },
    "showGrid": {
      "default": true,
      "description": "Show subtle grid lines behind the chart.",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show legend for multi-series charts. Auto-hidden when there is only one series.",
      "type": "boolean"
    },
    "rotateLabels": {
      "default": true,
      "description": "Rotate x-axis labels -45 degrees. Useful for long date strings.",
      "type": "boolean"
    },
    "xAxisFontSize": {
      "default": 11,
      "description": "Font size for x-axis labels in pixels.",
      "type": "number"
    },
    "yAxisFontSize": {
      "default": 11,
      "description": "Font size for y-axis labels in pixels.",
      "type": "number"
    },
    "bottomMargin": {
      "description": "Bottom margin in pixels. Overrides the auto-calculated value from rotateLabels. Useful when labels are clipped.",
      "type": "number"
    },
    "beginAtZero": {
      "default": true,
      "description": "Force the y-axis to start at 0. Ignored if yMin is set.",
      "type": "boolean"
    },
    "yMin": {
      "description": "Fixed minimum value for the y-axis. Overrides beginAtZero.",
      "type": "number"
    },
    "yMax": {
      "description": "Fixed maximum value for the y-axis.",
      "type": "number"
    },
    "animationMs": {
      "default": 300,
      "description": "Animation duration in milliseconds. 0 disables animation. Animation only plays on data changes, not on zoom/resize.",
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"padding: 8px; background-color: #1a1a1a\")",
      "type": "string"
    }
  },
  "required": [
    "sql"
  ],
  "description": "A line/area chart for time series data, powered by DuckDB SQL queries. Query must return 'label' and 'value' columns. Add a 'series' column for multiple lines.\n\n## Example\n\n```json\n{\n  \"type\": \"line-chart\",\n  \"props\": {\n    \"sql\": \"SELECT date AS label, revenue AS value FROM {{sales}} ORDER BY 1\",\n    \"title\": \"Revenue Over Time\"\n  }\n}\n```\n\n## Example \u2014 multi-series\n\n```json\n{\n  \"type\": \"line-chart\",\n  \"props\": {\n    \"sql\": \"SELECT date AS label, count AS value, category AS series FROM {{events}} ORDER BY 1, 3\",\n    \"title\": \"Events by Category\",\n    \"showArea\": true,\n    \"curveType\": \"smooth\"\n  }\n}\n```"
}
~~~

## map

Live UDF map.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label above the map",
      "type": "string"
    },
    "param": {
      "description": "Canvas parameter for bounds [west, south, east, north]",
      "type": "string"
    },
    "sendParam": {
      "default": false,
      "description": "Whether to send the bounds to the canvas",
      "type": "boolean"
    },
    "centerLng": {
      "default": -74,
      "type": "number"
    },
    "centerLat": {
      "default": 40.7,
      "type": "number"
    },
    "zoom": {
      "default": 12,
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"border-radius: 8px; overflow: hidden\")",
      "type": "string"
    },
    "layers": {
      "type": "array",
      "items": {
        "anyOf": [
          {
            "type": "object",
            "properties": {
              "udf": {
                "type": "string",
                "description": "Name of the UDF"
              },
              "visible": {
                "description": "Whether the layer is visible",
                "type": "boolean"
              },
              "vizConfig": {
                "description": "Visualization configuration for the layer",
                "type": "object",
                "propertyNames": {
                  "type": "string"
                },
                "additionalProperties": {}
              },
              "tile": {
                "description": "Connect as tile mode. By default layers connect as viewport (fetches data for the current map view as a single request).",
                "type": "boolean"
              }
            },
            "required": [
              "udf"
            ]
          },
          {
            "type": "string",
            "description": "Name of the UDF"
          }
        ],
        "description": "Layer configuration or UDF name"
      }
    },
    "mapStyle": {
      "description": "Map style",
      "type": "string",
      "enum": [
        "light",
        "dark",
        "satellite",
        "blank"
      ]
    },
    "autoFit": {
      "default": true,
      "description": "Automatically fit the map viewport to the loaded data bounds. When true, the map zooms once to frame the union of all layers' data after they first load, then leaves the viewport under user control (it does not re-fit on later pans or re-runs). When false, the map opens at centerLng/centerLat/zoom.",
      "type": "boolean"
    }
  },
  "required": [
    "layers"
  ],
  "description": "Interactive Mapbox map that renders live UDF layers. UDF names must use `{{double-brace}}` syntax. A UDF that returns a GeoDataFrame renders by default. A plain DataFrame renders only with a matching vizConfig \u2014 e.g. a DataFrame with an H3 `hex` column rendered via a `hexLayer` (H3HexagonLayer). A plain DataFrame with only lat/lon columns won't render here; use the `fused-map` widget's geojson layer for that.\n\n## Example \u2014 points\n\n```json\n{\n  \"type\": \"map\",\n  \"props\": {\n    \"centerLng\": -122.43,\n    \"centerLat\": 37.76,\n    \"zoom\": 11,\n    \"mapStyle\": \"dark\",\n    \"layers\": [\"{{my_udf}}\"]\n  }\n}\n```\n\n## Example \u2014 polygons\n\n```json\n{\n  \"type\": \"map\",\n  \"props\": {\n    \"centerLng\": -74,\n    \"centerLat\": 40.7,\n    \"zoom\": 10,\n    \"mapStyle\": \"dark\",\n    \"sendParam\": true,\n    \"autoFit\": true,\n    \"layers\": [\n      {\n        \"udf\": \"{{my_udf}}\"\n      }\n    ]\n  }\n}\n```\n\n## Example \u2014 tile layer\n\n```json\n{\n  \"type\": \"map\",\n  \"props\": {\n    \"layers\": [\n      {\n        \"udf\": \"{{my_udf}}\",\n        \"tile\": true,\n        \"vizConfig\": {\n          \"tileLayer\": {\n            \"@@type\": \"TileLayer\",\n            \"minZoom\": 0,\n            \"maxZoom\": 19,\n            \"tileSize\": 256\n          },\n          \"vectorLayer\": {\n            \"@@type\": \"GeoJsonLayer\",\n            \"stroked\": true,\n            \"filled\": false,\n            \"lineWidthMinPixels\": 1\n          }\n        }\n      }\n    ]\n  }\n}\n```\n\n## Example \u2014 H3 hexagons (plain DataFrame with a `hex` column)\n\n```json\n{\n  \"type\": \"map\",\n  \"props\": {\n    \"layers\": [\n      {\n        \"udf\": \"{{my_h3_udf}}\",\n        \"vizConfig\": {\n          \"hexLayer\": {\n            \"@@type\": \"H3HexagonLayer\",\n            \"stroked\": true,\n            \"filled\": true,\n            \"pickable\": true,\n            \"extruded\": false,\n            \"opacity\": 1,\n            \"coverage\": 0.9,\n            \"lineWidthMinPixels\": 5,\n            \"getHexagon\": \"@@=properties.hex\",\n            \"getFillColor\": [255, 165, 0, 180],\n            \"getLineColor\": [200, 200, 200, 255]\n          }\n        }\n      }\n    ]\n  }\n}\n```\n\n## Example \u2014 raster tile layer\n\n```json\n{\n  \"type\": \"map\",\n  \"props\": {\n    \"centerLng\": -122.43,\n    \"centerLat\": 37.76,\n    \"zoom\": 11,\n    \"mapStyle\": \"dark\",\n    \"layers\": [\n      {\n        \"udf\": \"{{my_raster_udf}}\",\n        \"tile\": true,\n        \"vizConfig\": {\n          \"tileLayer\": { \"@@type\": \"TileLayer\", \"minZoom\": 0, \"maxZoom\": 19, \"tileSize\": 256 },\n          \"rasterLayer\": { \"@@type\": \"BitmapLayer\", \"opacity\": 0.7 }\n        }\n      }\n    ]\n  }\n}\n```\n\nHere `my_raster_udf` returns a raster array (e.g. via `arr_to_plasma`)."
}
~~~

## map-bounds

Map that syncs viewport bounds to param.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label above the map",
      "type": "string"
    },
    "param": {
      "description": "Canvas parameter for bounds [west, south, east, north]",
      "type": "string"
    },
    "centerLng": {
      "default": -74,
      "type": "number"
    },
    "centerLat": {
      "default": 40.7,
      "type": "number"
    },
    "zoom": {
      "default": 12,
      "type": "number"
    },
    "styleUrl": {
      "default": "mapbox://styles/mapbox/dark-v10",
      "type": "string"
    },
    "buttonLabel": {
      "default": "Send View",
      "type": "string"
    },
    "autoSend": {
      "default": false,
      "type": "boolean"
    },
    "autoSendDebounceMs": {
      "default": 600,
      "type": "number"
    },
    "showSearch": {
      "default": false,
      "description": "Show a geocoder search bar overlay on the map.",
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"border-radius: 8px; overflow: hidden\")",
      "type": "string"
    }
  },
  "description": "Interactive Mapbox map that syncs viewport bounds [west, south, east, north] with a canvas parameter. Supports auto-send on pan/zoom or manual send via button.\n\n## Example\n\n```json\n{\n  \"type\": \"map-bounds\",\n  \"props\": {\n    \"param\": \"viewport\",\n    \"centerLng\": -74,\n    \"centerLat\": 40.7,\n    \"zoom\": 12,\n    \"autoSend\": true\n  }\n}\n```"
}
~~~

## map-h3

Map that emits H3 cell at center.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label above the map",
      "type": "string"
    },
    "param": {
      "description": "Canvas parameter for the H3 cell string",
      "type": "string"
    },
    "paramType": {
      "default": "string",
      "description": "Emit the H3 cell as a hex string (\"string\") or as a BigInt number (\"int\").",
      "type": "string",
      "enum": [
        "string",
        "int"
      ]
    },
    "centerLng": {
      "default": -74,
      "type": "number"
    },
    "centerLat": {
      "default": 40.7,
      "type": "number"
    },
    "zoom": {
      "default": 12,
      "type": "number"
    },
    "h3Res": {
      "description": "Fixed H3 resolution (0-15). If omitted, resolution is auto-derived from the map zoom level.",
      "type": "integer",
      "minimum": 0,
      "maximum": 15
    },
    "resOffset": {
      "default": 0,
      "description": "Offset added to the auto-derived resolution. Positive = smaller hexes, negative = bigger hexes.",
      "type": "integer",
      "minimum": -9007199254740991,
      "maximum": 9007199254740991
    },
    "hexColor": {
      "default": "#E8FF59",
      "description": "Hex outline & fill color.",
      "type": "string"
    },
    "hexOpacity": {
      "default": 0.03,
      "description": "Hex fill opacity. 0 = transparent, 1 = solid. Default 0.03 for a very slight fill.",
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "showDetails": {
      "default": true,
      "description": "Show hex ID and resolution overlay on the map.",
      "type": "boolean"
    },
    "styleUrl": {
      "default": "mapbox://styles/mapbox/dark-v11",
      "type": "string"
    },
    "showBasemapSwitcher": {
      "default": true,
      "description": "Show Dark / Light / Satellite basemap toggle on the map.",
      "type": "boolean"
    },
    "buttonLabel": {
      "default": "Send H3 cell",
      "type": "string"
    },
    "autoSend": {
      "default": false,
      "type": "boolean"
    },
    "autoSendDebounceMs": {
      "default": 300,
      "type": "number"
    },
    "sendOnMove": {
      "default": false,
      "description": "When true and autoSend is true, emit when the hex changes while dragging/zooming (debounce defaults to 0). When false, emit only when movement ends.",
      "type": "boolean"
    },
    "maxZoom": {
      "description": "Maximum zoom level. If omitted and h3Res is set, defaults to the zoom ceiling for that resolution so the user cannot zoom past the hex size.",
      "type": "number"
    },
    "minZoom": {
      "description": "Minimum zoom level. Prevents zooming out beyond this level.",
      "type": "number"
    },
    "latParam": {
      "description": "Canvas parameter name to emit the center latitude.",
      "type": "string"
    },
    "lngParam": {
      "description": "Canvas parameter name to emit the center longitude.",
      "type": "string"
    },
    "resParam": {
      "description": "Canvas parameter name to emit the current H3 resolution.",
      "type": "string"
    },
    "zoomParam": {
      "description": "Canvas parameter name to emit the current zoom level.",
      "type": "string"
    },
    "boundsParam": {
      "description": "Canvas parameter name to emit the viewport bounds as \"west,south,east,north\".",
      "type": "string"
    },
    "kRing": {
      "default": 0,
      "description": "K-ring radius around the center hex. 0 = center only. 1-6 = include surrounding rings.",
      "type": "integer",
      "minimum": 0,
      "maximum": 6
    },
    "kRingParam": {
      "description": "Canvas parameter name to emit a JSON array of all hex IDs in the k-ring (includes center).",
      "type": "string"
    },
    "showSearch": {
      "default": false,
      "description": "Show a geocoder search bar overlay on the map.",
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string",
      "type": "string"
    }
  },
  "description": "Interactive map that emits the H3 hex cell at the map center. Resolution can be fixed or auto-derived from zoom.\n\n## Example \u2014 auto-resolution, send on move\n\n```json\n{\n  \"type\": \"map-h3\",\n  \"props\": {\n    \"param\": \"hex_id\",\n    \"autoSend\": true,\n    \"sendOnMove\": true\n  }\n}\n```\n\n## Example \u2014 fixed resolution\n\n```json\n{\n  \"type\": \"map-h3\",\n  \"props\": {\n    \"param\": \"hex_id\",\n    \"h3Res\": 7,\n    \"centerLng\": -74,\n    \"centerLat\": 40.7\n  }\n}\n```"
}
~~~

## metric

Dashboard metric card with formatted value.

~~~json
{
  "type": "object",
  "properties": {
    "value": {
      "default": "",
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL with {{udf_name}} and $param_name placeholders. Returns first column of first row.",
      "type": "string"
    },
    "label": {
      "type": "string"
    },
    "prefix": {
      "default": "",
      "type": "string"
    },
    "suffix": {
      "default": "",
      "type": "string"
    },
    "format": {
      "default": "compact",
      "description": "How to format the number. \"compact\" abbreviates large values (e.g. 1.2M, 45.3K, 2.5B). \"comma\" adds thousand separators (e.g. 1,234,567). \"none\" displays the raw value as-is.",
      "type": "string",
      "enum": [
        "compact",
        "comma",
        "none"
      ]
    },
    "decimals": {
      "default": 1,
      "type": "number"
    },
    "size": {
      "default": 36,
      "description": "Font size of the number in pixels. e.g. 24, 36, 48, 72, 96, 144. Default 36.",
      "type": "number"
    },
    "color": {
      "type": "string"
    },
    "style": {
      "type": "string"
    }
  },
  "description": "Metric card for dashboards. Shows a single large formatted value from SQL, $param substitution in value, or a static value.\n\n## Example \u2014 SQL\n\n```json\n{\n  \"type\": \"metric\",\n  \"props\": {\n    \"sql\": \"SELECT COUNT(*) FROM {{my_udf}}\",\n    \"label\": \"Total Records\",\n    \"format\": \"compact\"\n  }\n}\n```\n\n## Example \u2014 static / param\n\n```json\n{\n  \"type\": \"metric\",\n  \"props\": {\n    \"value\": \"$record_count\",\n    \"label\": \"Records\",\n    \"suffix\": \" rows\",\n    \"format\": \"comma\"\n  }\n}\n```"
}
~~~

## number-input

Number input with optional param sync.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the number input",
      "type": "string"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular number input.",
      "type": "string"
    },
    "placeholder": {
      "default": "Enter number...",
      "type": "string"
    },
    "defaultValue": {
      "default": 0,
      "type": "number"
    },
    "min": {
      "type": "number"
    },
    "max": {
      "type": "number"
    },
    "step": {
      "default": 1,
      "type": "number",
      "exclusiveMinimum": 0
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "readOnly": {
      "default": false,
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "description": "A numeric input that can optionally sync valid number values with canvas parameters. If param is provided, syncs with that parameter or form; otherwise works as a regular number input.\n\n## Example\n\n```json\n{\n  \"type\": \"number-input\",\n  \"props\": {\n    \"label\": \"Max price\",\n    \"param\": \"max_price\",\n    \"min\": 0,\n    \"max\": 1000,\n    \"step\": 50,\n    \"defaultValue\": 500\n  }\n}\n```"
}
~~~

## pdf-gallery-viewer

Gallery viewer with thumbnail rail, page preview, navigation, and PDF download from SQL or static pages.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the widget",
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return value, title, and image columns. Takes precedence over pages.",
      "type": "string"
    },
    "pages": {
      "description": "Static array of pages. Used when sql is not provided or when sql fails.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "value": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "object",
                "propertyNames": {
                  "type": "string"
                },
                "additionalProperties": {}
              }
            ]
          },
          "title": {
            "type": "string",
            "description": "Title displayed under the thumbnail"
          },
          "image": {
            "type": "string",
            "description": "Image URL or base64 data URL used for thumbnail, preview, and PDF export"
          }
        },
        "required": [
          "value",
          "title",
          "image"
        ],
        "description": "A single page with value, title, and image."
      }
    },
    "defaultPageIndex": {
      "default": 0,
      "description": "Initial selected page index (0-based).",
      "type": "number"
    },
    "mode": {
      "default": "vertical",
      "description": "Layout mode. vertical places thumbnails on the left; horizontal places thumbnails on top.",
      "type": "string",
      "enum": [
        "vertical",
        "horizontal"
      ]
    },
    "thumbnailWidth": {
      "default": 120,
      "description": "Thumbnail card width in pixels.",
      "type": "number",
      "exclusiveMinimum": 0
    },
    "thumbnailHeight": {
      "default": 90,
      "description": "Thumbnail card height in pixels.",
      "type": "number",
      "exclusiveMinimum": 0
    },
    "previewHeight": {
      "default": 400,
      "description": "Preview pane height in pixels.",
      "type": "number",
      "exclusiveMinimum": 0
    },
    "pdfFileName": {
      "default": "document.pdf",
      "description": "Downloaded PDF file name.",
      "type": "string"
    },
    "downloadEnabled": {
      "default": true,
      "description": "If true, shows the download PDF button in the preview toolbar.",
      "type": "boolean"
    },
    "navigationEnabled": {
      "default": true,
      "description": "If true, shows previous and next page buttons in the preview toolbar.",
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"height: 100%; min-height: 480px\")",
      "type": "string"
    }
  },
  "description": "PDF/gallery viewer with thumbnail rail, full-page preview, navigation, and browser-side PDF download. Prefer sql for dynamic pages from UDF DataFrames; fall back to pages array for static data."
}
~~~

## scatter-chart

Scatter chart driven by DuckDB SQL query.

~~~json
{
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'x' and 'y'. Optional: 'series', 'size', 'label'."
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "pointColor": {
      "default": "#E8FF59",
      "description": "Point color for single-series charts.",
      "type": "string"
    },
    "pointOpacity": {
      "default": 0.85,
      "description": "Point opacity from 0 to 1.",
      "type": "number"
    },
    "defaultPointSize": {
      "default": 70,
      "description": "Default point size when SQL does not return a size column.",
      "type": "number"
    },
    "pointStrokeWidth": {
      "default": 0.5,
      "description": "Outline width of points in pixels.",
      "type": "number"
    },
    "pointStrokeColor": {
      "default": "#111827",
      "description": "Outline color for points.",
      "type": "string"
    },
    "minBubbleSize": {
      "default": 10,
      "description": "Minimum rendered bubble size when using a size column.",
      "type": "number"
    },
    "maxBubbleSize": {
      "default": 160,
      "description": "Maximum rendered bubble size when using a size column.",
      "type": "number"
    },
    "showGrid": {
      "default": true,
      "description": "Show subtle grid lines behind points.",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show legend when multiple series are present.",
      "type": "boolean"
    },
    "xAxisFontSize": {
      "default": 11,
      "description": "X-axis label font size in pixels.",
      "type": "number"
    },
    "yAxisFontSize": {
      "default": 11,
      "description": "Y-axis label font size in pixels.",
      "type": "number"
    },
    "xMin": {
      "description": "Fixed minimum value for x-axis.",
      "type": "number"
    },
    "xMax": {
      "description": "Fixed maximum value for x-axis.",
      "type": "number"
    },
    "yMin": {
      "description": "Fixed minimum value for y-axis.",
      "type": "number"
    },
    "yMax": {
      "description": "Fixed maximum value for y-axis.",
      "type": "number"
    },
    "animationMs": {
      "default": 300,
      "description": "Animation duration in milliseconds. 0 disables animation. Animation only plays on data changes, not on zoom/resize.",
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string.",
      "type": "string"
    }
  },
  "required": [
    "sql"
  ],
  "description": "A scatter chart powered by DuckDB SQL. Query must return x and y numeric columns.\n\n## Example\n\n```json\n{\n  \"type\": \"scatter-chart\",\n  \"props\": {\n    \"sql\": \"SELECT price AS x, rating AS y FROM {{listings}}\",\n    \"title\": \"Price vs. Rating\"\n  }\n}\n```"
}
~~~

## slider

A slider that can optionally sync with canvas parameters. If param is provided, syncs with that parameter or form; otherwise works as a regular slider.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the slider",
      "type": "string"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular slider.",
      "type": "string"
    },
    "min": {
      "default": 0,
      "type": "number"
    },
    "max": {
      "default": 100,
      "type": "number"
    },
    "step": {
      "default": 1,
      "type": "number"
    },
    "defaultValue": {
      "default": 0,
      "type": "number"
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "description": "A slider that syncs with canvas parameters. Works standalone or nested inside a `form`. Broadcasts value changes on a debounced basis.\n\n## Example\n\n```json\n{\n  \"type\": \"slider\",\n  \"props\": {\n    \"label\": \"Max price\",\n    \"param\": \"max_price\",\n    \"min\": 0,\n    \"max\": 1000,\n    \"step\": 50,\n    \"defaultValue\": 500\n  }\n}\n```"
}
~~~

## sql-runner

Named SQL source for descendant components.

~~~json
{
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "DuckDB SQL query with {{source_name}} and $param_name placeholders. The result becomes available to descendant SQL widgets as {{name}}."
    },
    "name": {
      "type": "string",
      "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$",
      "description": "Logical source name exposed to descendant SQL widgets via {{name}}."
    },
    "maxRows": {
      "default": 10000,
      "description": "Safety limit appended when the SQL has no LIMIT clause. Defaults to 10000.",
      "type": "integer",
      "exclusiveMinimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "sql",
    "name"
  ],
  "description": "Runs a DuckDB query and exposes its result as a named SQL source to descendant components. Children reference the result via {{name}}.\n\n## Example\n\n```json\n{\n  \"type\": \"sql-runner\",\n  \"props\": {\n    \"name\": \"filtered_data\",\n    \"sql\": \"SELECT * FROM {{my_udf}} WHERE price < $max_price\",\n    \"maxRows\": 10000\n  },\n  \"children\": [\n    { \"type\": \"bar-chart\", \"props\": { \"sql\": \"SELECT category AS label, COUNT(*) AS value FROM {{filtered_data}} GROUP BY 1\" } }\n  ]\n}\n```"
}
~~~

## sql-table

Table rendered from a DuckDB SQL query.

~~~json
{
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Example: SELECT * FROM {{my_udf}} LIMIT 100"
    },
    "title": {
      "description": "Table title displayed above",
      "type": "string"
    },
    "sortable": {
      "default": true,
      "description": "Allow sorting rows by clicking column headers",
      "type": "boolean"
    },
    "filterable": {
      "default": false,
      "description": "Show filter inputs below column headers",
      "type": "boolean"
    },
    "maxRows": {
      "default": 500,
      "description": "Safety limit appended when the SQL query has no LIMIT clause. Defaults to 500.",
      "type": "integer",
      "exclusiveMinimum": 0,
      "maximum": 9007199254740991
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"padding: 8px; height: 400px\")",
      "type": "string"
    },
    "aiBuilderMode": {
      "default": false,
      "description": "Whether the AI chat is active. When true, shows the AI chat panel. AI actions require authentication.",
      "type": "boolean"
    },
    "aiPanel": {
      "default": "right",
      "description": "Side the AI chat panel is docked on when aiBuilderMode is true.",
      "type": "string",
      "enum": [
        "left",
        "right"
      ]
    },
    "showEditor": {
      "default": false,
      "description": "Show a collapsible editor panel for inspecting and editing the current value.",
      "type": "boolean"
    },
    "editorPosition": {
      "default": "bottom",
      "description": "Place the editor panel above or below the component.",
      "type": "string",
      "enum": [
        "top",
        "bottom"
      ]
    },
    "editorCollapsed": {
      "default": false,
      "description": "Whether the editor panel starts collapsed.",
      "type": "boolean"
    },
    "editorHeight": {
      "description": "Optional initial editor height in pixels. If omitted, height auto-fits the current content.",
      "type": "number"
    }
  },
  "required": [
    "sql"
  ],
  "description": "Renders the results of a DuckDB SQL query in a table similar to the UDF node Data Table. Supports {{udf_name}} placeholders and $param_name canvas parameters. Optional AI chat can author the SQL for you.\n\n## Example\n\n```json\n{\n  \"type\": \"sql-table\",\n  \"props\": {\n    \"sql\": \"SELECT * FROM {{my_udf}} WHERE city = $city LIMIT 100\",\n    \"title\": \"Results\",\n    \"sortable\": true,\n    \"maxRows\": 500\n  }\n}\n```"
}
~~~

## stacked-area-chart

Stacked area chart driven by DuckDB SQL query.

~~~json
{
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'label', 'series', and 'value' columns."
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "areaOpacity": {
      "default": 0.6,
      "description": "Opacity of each stacked area from 0 to 1.",
      "type": "number"
    },
    "curveType": {
      "default": "smooth",
      "description": "Interpolation curve type.",
      "type": "string",
      "enum": [
        "linear",
        "smooth",
        "step"
      ]
    },
    "showGrid": {
      "default": true,
      "description": "Show subtle grid lines behind the chart.",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show legend for stacked series.",
      "type": "boolean"
    },
    "showBrush": {
      "default": true,
      "description": "Show brush slider for range selection.",
      "type": "boolean"
    },
    "brushHeight": {
      "default": 30,
      "description": "Height of brush slider in pixels.",
      "type": "number"
    },
    "rotateLabels": {
      "default": true,
      "description": "Rotate x-axis labels by -45 degrees.",
      "type": "boolean"
    },
    "xAxisFontSize": {
      "default": 11,
      "description": "X-axis label font size in pixels.",
      "type": "number"
    },
    "yAxisFontSize": {
      "default": 11,
      "description": "Y-axis label font size in pixels.",
      "type": "number"
    },
    "beginAtZero": {
      "default": true,
      "description": "Force y-axis to start at zero.",
      "type": "boolean"
    },
    "yMin": {
      "description": "Fixed minimum y-axis value.",
      "type": "number"
    },
    "yMax": {
      "description": "Fixed maximum y-axis value.",
      "type": "number"
    },
    "bottomMargin": {
      "description": "Override bottom margin in pixels.",
      "type": "number"
    },
    "animationMs": {
      "default": 300,
      "description": "Animation duration in milliseconds. 0 disables animation. Animation only plays on data changes, not on zoom/resize.",
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string.",
      "type": "string"
    }
  },
  "required": [
    "sql"
  ],
  "description": "A stacked area chart powered by DuckDB SQL. Query should return label, series, and value.\n\n## Example\n\n```json\n{\n  \"type\": \"stacked-area-chart\",\n  \"props\": {\n    \"sql\": \"SELECT month AS label, revenue AS value, category AS series FROM {{sales}} ORDER BY 1\",\n    \"title\": \"Revenue by Category\"\n  }\n}\n```"
}
~~~

## stacked-bar-chart

Stacked bar chart driven by DuckDB SQL query.

~~~json
{
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'label', 'series', and 'value' columns."
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "horizontal": {
      "default": false,
      "description": "Render horizontal stacked bars.",
      "type": "boolean"
    },
    "showGrid": {
      "default": true,
      "description": "Show subtle grid lines behind bars.",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show legend for stacked series.",
      "type": "boolean"
    },
    "rotateLabels": {
      "default": true,
      "description": "Rotate x-axis labels by -45 degrees.",
      "type": "boolean"
    },
    "xAxisFontSize": {
      "default": 11,
      "description": "X-axis label font size in pixels.",
      "type": "number"
    },
    "yAxisFontSize": {
      "default": 11,
      "description": "Y-axis label font size in pixels.",
      "type": "number"
    },
    "beginAtZero": {
      "default": true,
      "description": "Force value axis to start at 0.",
      "type": "boolean"
    },
    "bottomMargin": {
      "description": "Override bottom margin in pixels.",
      "type": "number"
    },
    "animationMs": {
      "default": 300,
      "description": "Animation duration in milliseconds. 0 disables animation. Animation only plays on data changes, not on zoom/resize.",
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string.",
      "type": "string"
    }
  },
  "required": [
    "sql"
  ],
  "description": "A stacked bar chart powered by DuckDB SQL. Query should return label, series, and value.\n\n## Example\n\n```json\n{\n  \"type\": \"stacked-bar-chart\",\n  \"props\": {\n    \"sql\": \"SELECT quarter AS label, revenue AS value, region AS series FROM {{sales}} ORDER BY 1\",\n    \"title\": \"Revenue by Region\"\n  }\n}\n```"
}
~~~

## text

Static or dynamic text display.

~~~json
{
  "type": "object",
  "properties": {
    "value": {
      "default": "",
      "description": "The text value to display. Supports $param_name and {{udf_name}} placeholders that are substituted before display.",
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders (e.g., SELECT COUNT(*) as count FROM {{my_udf}}). Returns first row's first column value. Highest priority.",
      "type": "string"
    },
    "variant": {
      "default": "default",
      "description": "Text style variant",
      "type": "string",
      "enum": [
        "default",
        "muted",
        "small",
        "large",
        "h1",
        "h2",
        "h3",
        "h4"
      ]
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "description": "Displays text values. Can show static values, dynamic values from message parameters, or results from DuckDB SQL queries. Priority: sql > value.\n\n## Example \u2014 static / param\n\n```json\n{\n  \"type\": \"text\",\n  \"props\": {\n    \"value\": \"Selected city: $city\",\n    \"variant\": \"h3\"\n  }\n}\n```\n\n## Example \u2014 SQL\n\n```json\n{\n  \"type\": \"text\",\n  \"props\": {\n    \"sql\": \"SELECT COUNT(*) || ' records' FROM {{my_udf}}\",\n    \"variant\": \"muted\"\n  }\n}\n```"
}
~~~

## text-area

Multi-line text input with optional param sync.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the text area",
      "type": "string"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular text area.",
      "type": "string"
    },
    "placeholder": {
      "default": "Enter text...",
      "type": "string"
    },
    "defaultValue": {
      "default": "",
      "type": "string"
    },
    "submitMode": {
      "default": "type",
      "type": "string",
      "enum": [
        "type",
        "focus",
        "submit"
      ],
      "description": "Controls when the text area value is sent: type sends while typing, focus sends on blur, and submit sends only from the inline submit button or Enter key."
    },
    "debounceMs": {
      "default": 300,
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "rows": {
      "default": 4,
      "type": "integer",
      "minimum": 1,
      "maximum": 50
    },
    "maxLength": {
      "type": "integer",
      "exclusiveMinimum": 0,
      "maximum": 9007199254740991
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "readOnly": {
      "default": false,
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "description": "A multi-line text input that can optionally sync with canvas parameters. If param is provided, syncs with that parameter or form; otherwise works as a regular text area.\n\n## Example\n\n```json\n{\n  \"type\": \"text-area\",\n  \"props\": {\n    \"label\": \"Notes\",\n    \"param\": \"notes\",\n    \"placeholder\": \"Enter notes...\",\n    \"rows\": 4\n  }\n}\n```"
}
~~~

## text-input

Text input with optional param sync.

~~~json
{
  "type": "object",
  "properties": {
    "label": {
      "description": "Label text displayed above the input",
      "type": "string"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular input.",
      "type": "string"
    },
    "placeholder": {
      "default": "Enter value...",
      "type": "string"
    },
    "defaultValue": {
      "default": "",
      "type": "string"
    },
    "submitMode": {
      "default": "type",
      "type": "string",
      "enum": [
        "type",
        "focus",
        "submit"
      ],
      "description": "Controls when the input value is sent: type sends while typing, focus sends on blur, and submit sends only from the inline submit button or Enter key."
    },
    "debounceMs": {
      "default": 300,
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "type": {
      "default": "text",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "description": "A text input field that can optionally sync with canvas parameters. If param is provided, syncs with that parameter or form; otherwise works as a regular input.\n\n## Example\n\n```json\n{\n  \"type\": \"text-input\",\n  \"props\": {\n    \"label\": \"Search\",\n    \"param\": \"search_query\",\n    \"placeholder\": \"Enter search term...\"\n  }\n}\n```"
}
~~~

## transformer

Execute JS in a sandbox, broadcast result to a param.

~~~json
{
  "type": "object",
  "properties": {
    "param": {
      "type": "string",
      "description": "Canvas parameter name to broadcast the result to."
    },
    "method": {
      "type": "string",
      "description": "JavaScript code string. Contains $param_name and {{udf_name}} references that are substituted before execution."
    },
    "maxRows": {
      "default": 10000,
      "description": "Row limit for UDF data queries. Defaults to 10000.",
      "type": "integer",
      "exclusiveMinimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "param",
    "method"
  ],
  "description": "Non-visual component that runs JavaScript in a sandboxed iframe and broadcasts the return value to a canvas param. Use $param_name to inject canvas param values and {{udf_name}} to inject UDF result rows. UDF data is substituted as a JSON object of column arrays. The method string must be a no-argument arrow function that explicitly returns a value.\n\n## Example\n\n```json\n{\n  \"type\": \"transformer\",\n  \"props\": {\n    \"param\": \"price_tier\",\n    \"method\": \"() => { const p = Number($max_price); if (p <= 100) return 'Budget'; if (p <= 300) return 'Mid-range'; return 'Luxury'; }\"\n  }\n}\n```"
}
~~~

## video

Display a video from a URL, base64 data URL, or signable storage path.

~~~json
{
  "type": "object",
  "properties": {
    "src": {
      "type": "string",
      "description": "Video URL, base64 data URL, or signable storage path (e.g., \"s3://bucket/clip.mp4\")"
    },
    "alt": {
      "description": "Accessible description of the video",
      "type": "string"
    },
    "objectFit": {
      "default": "contain",
      "description": "How the video fits its container",
      "type": "string",
      "enum": [
        "contain",
        "cover",
        "fill",
        "none",
        "scale-down"
      ]
    },
    "controls": {
      "default": true,
      "description": "Whether to show native playback controls",
      "type": "boolean"
    },
    "autoPlay": {
      "default": false,
      "description": "Whether the video starts playing automatically",
      "type": "boolean"
    },
    "loop": {
      "default": false,
      "description": "Whether the video loops after ending",
      "type": "boolean"
    },
    "muted": {
      "default": false,
      "description": "Whether the video is muted (required for autoplay in most browsers)",
      "type": "boolean"
    },
    "playsInline": {
      "default": true,
      "description": "Whether the video should play inline on mobile devices",
      "type": "boolean"
    },
    "poster": {
      "description": "Poster image URL shown before playback starts",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"border-radius: 8px\")",
      "type": "string"
    }
  },
  "required": [
    "src"
  ],
  "description": "Displays a video from a URL, base64 data URL, or signable storage path."
}
~~~

## widget-builder

Builds and renders a widget from a param-supplied or inline definition object.

~~~json
{
  "type": "object",
  "properties": {
    "defaultValue": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "object",
          "propertyNames": {
            "type": "string"
          },
          "additionalProperties": {}
        }
      ],
      "description": "Widget definition to render. Use \"$param_name\" to read from a canvas param, or provide a literal { type, props } object."
    },
    "showEditor": {
      "default": true,
      "description": "Show a collapsible JSON editor panel for inspecting/editing the widget definition.",
      "type": "boolean"
    },
    "editorCollapsed": {
      "default": true,
      "description": "Whether the editor panel starts collapsed.",
      "type": "boolean"
    },
    "editorHeight": {
      "description": "Optional initial height in pixels. If omitted, height auto-fits JSON line count.",
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"padding: 8px\")",
      "type": "string"
    },
    "aiBuilderMode": {
      "default": true,
      "description": "Whether the AI widget builder is active. When true, shows the AI panel. AI actions require authentication.",
      "type": "boolean"
    },
    "aiModel": {
      "default": "Claude Sonnet 4.6",
      "description": "AI model used by the widget builder. Defaults to Claude Sonnet.",
      "type": "string",
      "enum": [
        "Claude Opus 4.6",
        "Claude Sonnet 4.6",
        "Claude Haiku 4.5",
        "GLM 4.7",
        "GPT OSS 120B",
        "Kimi K2.5",
        "GPT-5.4",
        "GPT-5.5",
        "Gemini 3.5 Flash",
        "Gemini 3 Flash Preview",
        "Gemini 3 Pro Preview"
      ]
    },
    "aiPanel": {
      "default": "right",
      "description": "Position of the AI panel when aiBuilderMode is true. 'top'/'bottom' show a compact input bar above/below the widget. 'left'/'right' show a full chat panel as a side column.",
      "type": "string",
      "enum": [
        "top",
        "bottom",
        "left",
        "right"
      ]
    },
    "allowedWidgetTypes": {
      "default": "all",
      "description": "Comma-separated list of widget types that may be rendered (e.g. \"div,text,text-input\"). Use \"all\" to allow every type.",
      "type": "string"
    },
    "initialPrompt": {
      "description": "When set and aiBuilderMode is true, this prompt is automatically submitted to the AI on first load.",
      "type": "string"
    }
  },
  "required": [
    "defaultValue"
  ],
  "description": "Renders a widget definition received via a canvas param or inline. Use \"$param_name\" to render whatever a dropdown (or other sender) broadcasts. Set showEditor to enable a live JSON editor panel.\n\n## Example \u2014 from param\n\n```json\n{\n  \"type\": \"widget-builder\",\n  \"props\": {\n    \"defaultValue\": \"$widget_definition\",\n    \"showEditor\": true\n  }\n}\n```\n\n## Example \u2014 inline definition\n\n```json\n{\n  \"type\": \"widget-builder\",\n  \"props\": {\n    \"defaultValue\": {\n      \"type\": \"metric\",\n      \"props\": { \"sql\": \"SELECT COUNT(*) FROM {{my_udf}}\", \"label\": \"Total rows\" }\n    },\n    \"showEditor\": false\n  }\n}\n```"
}
~~~
