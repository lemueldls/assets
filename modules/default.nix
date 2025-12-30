{ inputs, pkgs, ... }:
let
  iosevka = pkgs.callPackage ./iosevka { inherit inputs; };
in
{
  iosevka-book = iosevka.book;
  iosevka-code = iosevka.code;
  iosevka-term = iosevka.term;
}
