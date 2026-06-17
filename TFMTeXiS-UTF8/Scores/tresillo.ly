\version "2.22.1"

melody = \relative c' {
  \clef treble
  \key c \major
  \time 4/4
  
  % Compás 1: Una negra, un tresillo de corcheas (entra en 1 tiempo) y dos negras
  c4 \tuplet 3/2 { d8 e f } g4 g |
  
  % Compás 2: Un tresillo de negras (entra en 2 tiempos) y una blanca para cerrar
  \tuplet 3/2 { a4 g f } e2 \bar "|."
}

\score {
  \new Staff { \melody }
  \layout { }
  \midi { }
}