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
  }

  \layout {
    ragged-right = ##t
  }
}