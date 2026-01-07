{ inputs, pkgs, ... }:
let
  iosevka = pkgs.callPackage ./iosevka { inherit inputs; };
in
{
  iosevka-book = iosevka.book;
  iosevka-slim = iosevka.slim;
  iosevka-code = iosevka.code;
  iosevka-term = iosevka.term;

  sarasa-gothic = pkgs.callPackage ./sarasa-gothic.nix { inherit inputs; };

  walls = pkgs.callPackage ./walls.nix { inherit inputs; };
}
