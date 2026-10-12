{
  description = "Public assets";

  inputs = {
    nixpkgs.url = "nixpkgs/nixos-unstable";

    flake-utils.url = "github:numtide/flake-utils";

    iosevka-upstream = {
      url = "github:be5invis/Iosevka";
      flake = false;
    };

    rubify = {
      url = "github:lemueldls/rubify";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    wallpapers = {
      url = ./modules/wallpapers/images;
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
        packages = modules // {
          default = pkgs.buildEnv {
            name = "assets";
            paths = [
              modules.wallpapers
              modules.fonts.asterism-text
              modules.fonts.asterism-slim
              modules.fonts.asterism-code
              modules.fonts.asterism-term
              modules.fonts.asterism-ruby
            ];
          };
        };

        apps.publish = {
          type = "app";
          program = "${modules.publish}/bin/publish";
        };
      }
    );
}
