\version "2.22.1"

\header {
  title = "Corre, caballo"
  composer = "Lénica Reyes Zúñiga"
  arranger = "José Miguel Hernández Jaramillo"
  copyright = "PTNera Consulting SL (1950)"
}

melody = \absolute {
  \clef treble
  \key f \major
  \time 6/8
  
  \partial 4.
  c'8 c'8 c'8 |
  
  f'4 f'8 f'8 e'8 f'8 |
  
  g'4 g'8 c'8 c'8 c'8 |
  
  g'4 g'8 g'8 f'8 e'8 |
  
  f'4 f'8 \bar "|."
}

text = \lyricmode {
  Co -- rre ca -- ba -- llo,
  co -- rre li -- ge -- ro,
  ga -- na la gue -- rra
  "de el" ga -- lli -- ne -- ro.
}

\score {
  <<
    \new Staff {
      \new Voice = "mel" { \melody }
    }
    \new Lyrics \lyricsto "mel" { \text }
  >>
  \layout { }
  \midi { }
}