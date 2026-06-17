\version "2.24.0"

\paper {
  indent = 0
  line-width = 10\cm
}

\score {
  \new Staff {
    \clef treble
    \time 2/4

    c'8 d'4 c'8 |

    c'8 e'4 d'8 |
  }

  \layout {
    ragged-right = ##t
  }
}