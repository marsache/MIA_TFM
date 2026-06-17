\version "2.24.0"

\paper {
  indent = 0
  line-width = 10\cm
}

\score {
  \new Staff {
    \clef treble
    \key d \major

    \time 6/8
    \partial 4
    fis'8[ g'8] |

    a'8[ a'8 a'8] a'8[ a'8 a'8] |

    \once \override TextScript.extra-offset = #'(0 . 3)
    s2^\markup { \fontsize #3 "⋯" }

    \time 3/4
    d'2 r4
    \bar "|."
  }

  \layout {
    ragged-right = ##t
  }
}