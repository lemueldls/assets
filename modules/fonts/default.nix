{ inputs, pkgs, ... }:
let
  asterism = pkgs.callPackage ./asterism { inherit inputs; };
in
{
  asterism-text = asterism.text;
  asterism-slim = asterism.slim;
  asterism-code = asterism.code;
  asterism-term = asterism.term;

  asterism-ruby = pkgs.callPackage ./asterism/ruby.nix { inherit inputs; };
}
