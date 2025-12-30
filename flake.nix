{
  description = "Public assets";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";

    flake-utils = {
      url = "github:numtide/flake-utils";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    iosevka-upstream = {
      url = "github:be5invis/Iosevka";
      flake = false;
    };
  };

  outputs =
    inputs:
    inputs.flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import inputs.nixpkgs { inherit system; };
        modules = pkgs.callPackage ./modules { inherit inputs; };
      in
      {
        packages = {
          default = pkgs.buildEnv {
            name = "assets";
            paths = with modules; [
              iosevka-book
              iosevka-code
              iosevka-term
            ];
          };

          inherit (modules) iosevka-book iosevka-code iosevka-term;
        };
      }
    );
}
