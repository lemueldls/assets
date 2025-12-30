{ inputs, pkgs, ... }:
let
  iosevka = pkgs.callPackage ./iosevka { inherit inputs; };
in
{
  packages = [
    iosevka.book
    iosevka.code
    iosevka.term
    # nerd-fonts-symbols =  nerd-fonts.symbols-only
    # pkgs.recursive
    # sarasa-gothic
    # noto-fonts-color-emoji
    # material-symbols
    # symbola
  ];
}
