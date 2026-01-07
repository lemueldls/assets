{
  inputs,
  lib,
  stdenvNoCC,

  # Deps
  lutgen,
}:

let
  name = "walls";
  src = inputs.wallpapers;
in

stdenvNoCC.mkDerivation (finalAttrs: {
  inherit name src;

  installPhase = ''
    runHook preInstall

    ${lib.getExe lutgen} apply -p catppuccin-mocha *.{png,jpg} -- "#00a896"
    ${lib.getExe lutgen} apply -p catppuccin-latte *.{png,jpg} -- "#00a896"

    imgdir="${placeholder "out"}/share/wallpapers/lemueldls/contents/images"
    mkdir -p $imgdir
    cp -r * $imgdir

    runHook postInstall
  '';
})
