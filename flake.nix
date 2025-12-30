{
  description = "Public assets";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";

    iosevka-upstream = {
      url = "github:be5invis/Iosevka";
      flake = false;
    };
  };

  outputs =
    inputs:
    let
      system = "x86_64-linux";
      overlays = [ ];
      allowUnfree = true;
      pkgs = import inputs.nixpkgs {
        inherit system overlays;
        config.allowUnfree = allowUnfree;
      };
      fonts = pkgs.callPackage ./fonts { inherit inputs; };
    in
    {
      packages.${system}.default = pkgs.buildEnv {
        name = "assets";
        paths = fonts.packages ++ [ ];
      };
    };
}
