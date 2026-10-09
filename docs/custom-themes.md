# Custom themes

RigDeck comes with Light, Dark, Dracula, One Dark and Solarized Light. If none of those is quite
right, you can make your own as a small [JSON](https://www.json.org) file and use it the same way.

- **App:** Settings → *Appearance* → **Export theme template…** to get a starting file with your
  current theme's own colors, edit its colors, then **Import theme file…** to use it. It shows up
  in the theme picker and in *Your themes*, where it can be removed again.

## The file

A theme file is one JSON object: a `name`, and 7 colors.

```json
{
  "name": "My Theme",
  "window": "#101214",
  "panel": "#1c1e21",
  "raised": "#282c2f",
  "text": "#e2e5e8",
  "muted": "#90969c",
  "border": "#3a3e42",
  "accent": "#42a1f3"
}
```

| Key | Used for |
|---|---|
| `name` | Shown in the theme picker; also becomes the file's name on disk (lowercased, spaces → `-`) |
| `window` | The app's background, behind every panel |
| `panel` | Cards and panels raised above the window |
| `raised` | Buttons, inputs, and anything a step above `panel` |
| `text` | Body text |
| `muted` | Secondary text, placeholders, disabled text |
| `border` | Dividers and outlines |
| `accent` | Links, the active state, highlights |

Colors are written `"ff0000"` or `"#ff0000"`. Whether the theme counts as "dark" (for native
dialogs and the sun/moon toggle) is worked out automatically from `window`'s brightness — there's
nothing to set for that.

Importing the same `name` again replaces that theme rather than adding a second one.

## Where they live

Each theme is its own file in `~/.config/rigdeck/themes/` (e.g. `my-theme.json`). You can edit,
copy or remove them directly there too — RigDeck picks up the folder's contents again the next
time a theme is added or removed in Settings, or the app is restarted.
