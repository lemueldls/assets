{
  inputs,
  lib,
  pkgs,

  stdenv,
}:

let
  rubify = inputs.rubify.packages.${stdenv.hostPlatform.system}.default;
  iosevka = pkgs.callPackage ./iosevka { inherit inputs; };
in

pkgs.sarasa-gothic.overrideAttrs (finalAttrs: {
  installPhase = ''
    runHook preInstall

    mkdir -p $out/share/fonts/truetype
    for ttc_file in *.ttc; do
      ${lib.getExe rubify} $ttc_file --font ${iosevka.slim}/share/fonts/truetype/IosevkaSlim-Regular.ttf --subset -o $out/share/fonts/truetype
    done

    runHook postInstall
  '';
})
