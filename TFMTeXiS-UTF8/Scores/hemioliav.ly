\version "2.24.0"

\score {
  \new Staff <<
    \time 3/4

    \new Voice = "upper" {
      \voiceOne
      c''4. c''4. |
      c''4. c''4.
    }

    \new Voice = "lower" {
      \voiceTwo
      c'4 c'4 c'4 |
      c'4 c'4 c'4 |
    }
  >>

  \layout {
    ragged-right = ##t
  }
}