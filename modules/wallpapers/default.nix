{ inputs, pkgs, ... }:
{
  default = pkgs.callPackage ./package.nix { inherit inputs; };
}
