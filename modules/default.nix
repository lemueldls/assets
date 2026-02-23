{ inputs, pkgs, ... }:
{
  fonts = pkgs.callPackage ./fonts { inherit inputs; };
  wallpapers = pkgs.callPackage ./wallpapers { inherit inputs; };
}
