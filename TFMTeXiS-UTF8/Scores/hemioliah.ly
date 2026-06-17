\version "2.24.0"

\paper {
  indent = 0
  line-width = 12\cm
}

\score {
  \new Staff {
    \clef treble

    \time 6/8
    \set Timing.beatStructure = 3,3
    c'8 d' e'  f' g' a' |

    \set Timing.beatStructure = 2,2,2
    c'4 d' e' |
  }

  \layout {
    ragged-right = ##t
  }
}