{ inputs, pkgs, ... }:
let
  iosevka = pkgs.callPackage ./iosevka { inherit inputs; };
  asterism = pkgs.callPackage ./asterism { inherit inputs; };
in
{
  iosevka-book = iosevka.book;
  iosevka-slim = iosevka.slim;
  iosevka-code = iosevka.code;
  iosevka-term = iosevka.term;

  asterism-text = asterism.text;
  asterism-slim = asterism.slim;
  asterism-code = asterism.code;
  asterism-term = asterism.term;

  asterism-ruby = pkgs.callPackage ./asterism/ruby.nix { inherit inputs; };
}
