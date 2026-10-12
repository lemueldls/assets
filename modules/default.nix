{ inputs, pkgs, ... }:
let
  fonts = pkgs.callPackage ./fonts { inherit inputs; };
  wallpapers = pkgs.callPackage ./wallpapers { inherit inputs; };

  cuts = [
    fonts.asterism-text
    fonts.asterism-slim
    fonts.asterism-code
    fonts.asterism-term
  ];

  fontPackages = cuts ++ [ fonts.asterism-ruby ];

  python = pkgs.python3.withPackages (ps: [
    ps.pillow
    ps.numpy
  ]);

  metaFonts =
    pkgs.runCommand "fonts.meta.json"
      {
        nativeBuildInputs = [ pkgs.python3 ];
      }
      ''
        python ${./meta/fonts.py} --out $out \
          ${pkgs.lib.concatStringsSep " " (map (p: "${p}/share") fontPackages)}
      '';

  metaWalls =
    pkgs.runCommand "walls.meta.json"
      {
        nativeBuildInputs = [ python ];
      }
      ''
        python ${./meta/walls.py} --out $out \
          ${wallpapers}/share/wallpapers/assets/contents/images
      '';

  fontArchives = pkgs.callPackage ./fonts/zip.nix { inherit inputs; };

  publish = pkgs.writers.writePython3Bin "publish" {
    libraries = [ pkgs.python3Packages.boto3 ];
    flakeIgnore = [ "E501" ];
  } (builtins.readFile ./publish/publish.py);

  public = pkgs.runCommand "public" { } ''
    mkdir -p $out/fonts/truetype $out/fonts/woff2 $out/wallpapers

    for pkg in ${pkgs.lib.concatStringsSep " " fontPackages}; do
      for kind in truetype woff2; do
        if [ -d "$pkg/share/fonts/$kind" ]; then
          cp -rL "$pkg/share/fonts/$kind/." "$out/fonts/$kind/"
          chmod -R u+w "$out/fonts/$kind"
        fi
      done
    done

    cp -rL ${wallpapers}/share/wallpapers/assets/contents/images/. $out/wallpapers/

    chmod -R u+w $out

    cp ${metaFonts} $out/fonts.meta.json
    cp ${metaWalls} $out/walls.meta.json
    cp ${fontArchives}/*.zip $out/fonts/
  '';
in
{
  inherit
    fonts
    wallpapers
    metaFonts
    metaWalls
    fontArchives
    publish
    public
    ;
}
