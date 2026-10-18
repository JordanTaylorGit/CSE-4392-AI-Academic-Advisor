"""UI theme guard (Person E).

st.html sanitizes its input and silently drops a <style> block whose text
contains a raw "<", which unstyles the whole app. Write it as \\3C instead.
"""

from ui import theme


def test_theme_css_has_no_raw_less_than():
    css = theme.CSS.strip()
    assert css.startswith("<style>") and css.endswith("</style>")
    body = css[len("<style>"):-len("</style>")]
    assert "<" not in body
