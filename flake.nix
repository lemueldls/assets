{
  description = "Public assets";

  inputs = {
    nixpkgs.url = "nixpkgs/nixos-25.11";

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
            paths = with modules; [
              iosevka-book
              iosevka-slim
              iosevka-code
              iosevka-term
              sarasa-gothic
              wallpapers
            ];
          };
        };
      }
    );
}
