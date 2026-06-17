\version "2.24.0"

\paper {
  indent = 0
  line-width = 10\cm
  ragged-last = ##t
}

\header {
  title = "Arrullo mexicano"
  composer = "Guillermo Mora Reguera"
  tagline = ##f
}

\score {
  \new Staff {
    \clef treble
    \key f \major
    \time 5/4
    \tempo 4 = 90

    c'8[ c'8] c'8[ c'8] |

    f'4 f'2
    a'8[ c''8]
    bes'8[ a'8]
  }

  \layout {
    ragged-right = ##t
  }
}