{ inputs, pkgs, ... }:
{
  iosevka = pkgs.callPackage ./iosevka { inherit inputs; };
}
