# UI translation providers

User request 2026-10-26: provide switchable Chinese localization, including option
labels, option values and descriptions. Retain DS's existing locale and engagement
repairs. Navigation stays one integrated plugin.

Failure contracts before implementation:
- Enabling a provider changes persisted option values, control switches or language Params.
- Disabling/removing the provider leaves translated text or stale tile textures behind.
- A provider missing its exclusive claim, returning invalid metadata/text or raising
  crashes UI or stays active. Unknown text must fall back to the original/base locale.
- Only headings translate while buttons, choice values or plugin descriptions remain English.
- New Chinese glyphs are absent from the font atlas; measuring English before rendering
  Chinese clips or misaligns labels. Language toggles fail to invalidate text/tile caches.
- Imported catalogs alter protocol names, plugin ids, claim strings or numeric option values.
- A source check or screenshot is described as device activation or road validation.

Use the existing exclusive claim source:ui.translations and a generic Plugin
ui_translation(params) factory. The provider supplies language, glyphs and a pure
translate(text) method. Host UI polls active providers at most once a second,
validates returned text/locale, isolates failures and restores the existing locale
on disable. No provider writes Params, starts processes or uses vehicle hooks.

Multilang owns only the generic transient presentation overlay. Its generation
invalidates tile text caches and its extra glyphs extend the selected Noto atlas.
The provider's dictionary belongs in the store plugin, not the host. Original
English identifiers and option numeric values stay unchanged.

The upstream 196068-byte Chinese font is a subset: the first expanded catalog
has 240 missing glyphs. An optional provider font_path must be an ordinary font
inside that provider's own module directory, with a bounded size and valid font
header. Restore the base font when the provider is disabled or faults. Do not
overwrite the system font or upload all 44,810 full-font characters into an atlas.
