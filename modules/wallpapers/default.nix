{
  inputs,
  lib,
  stdenvNoCC,

  # Deps
  lutgen,
}:

let
  name = "wallpapers";
  src = inputs.wallpapers;

  cycle = [
    "dark/abstract-swirls.jpg"
    "dark/astronaut.png"
    "dark/basement.jpg"
    "dark/beach-path.jpg"
    "dark/bluehour.jpg"
    "dark/bunnies-road.png"
    "dark/cabin-3.png"
    "dark/cabin.png"
    "dark/cartoon-castle.png"
    "dark/car-wreck.png"
    "dark/city.png"
    "dark/clearing.png"
    "dark/clouds-2.png"
    "dark/clouds-3.jpg"
    "dark/clouds-3.png"
    "dark/clouds.png"
    "dark/cool.jpg"
    "dark/corals-fish-underwater.jpg"
    "dark/cottages-river.png"
    "dark/crane.png"
    "dark/dark-forest.jpg"
    "dark/dark-waves.jpg"
    "dark/degirled.png"
    "dark/diner-lonely-road.jpg"
    "dark/eclipse.jpg"
    "dark/firewatch.jpg"
    "dark/flying-comets-clouds.jpg"
    "dark/fw13-pro.png"
    "dark/galaxy-waves.jpg"
    "dark/gentlemen-sunset.png"
    "dark/greenbus.jpg"
    "dark/haunted-house.jpg"
    "dark/horizon.jpg"
    "dark/isekai.jpg"
    "dark/japan-alley.png"
    "dark/koi.jpg"
    "dark/lake-hylia.jpg"
    "dark/laundry.jpg"
    "dark/lighthouse-2.png"
    "dark/lighthouse.jpg"
    "dark/main-street.png"
    "dark/maji-no-tabitabi-3.jpg"
    "dark/map.png"
    "dark/marine-tunnel.jpg"
    "dark/math.png"
    "dark/min-forest.jpg"
    "dark/misty-boat.jpg"
    "dark/mountain-range.jpg"
    "dark/mushishi.jpg"
    "dark/myron.jpg"
    "dark/nature-valley-1.jpg"
    "dark/nature-valley-2.jpg"
    "dark/old-car.jpg"
    "dark/outset-island-day.jpg"
    "dark/outset-island-evening.jpg"
    "dark/outset-island-morning.jpg"
    "dark/outset-island-night.jpg"
    "dark/oversized-cat.jpg"
    "dark/painting.jpg"
    "dark/painting-standing.jpg"
    "dark/paint.jpg"
    "dark/pitstop.png"
    "dark/pixel-car.png"
    "dark/pixel-castle.png"
    "dark/platform.jpg"
    "dark/puffy-stars.jpg"
    "dark/purpled-night.jpg"
    "dark/purple-horizon.jpg"
    "dark/river-city.jpg"
    "dark/rocket-launch.jpg"
    "dark/rocket-schematics.jpg"
    "dark/rooftops.jpg"
    "dark/ruins.jpg"
    "dark/serenity.jpg"
    "dark/ship-2.png"
    "dark/ship-3.jpg"
    "dark/snowflakes.jpg"
    "dark/storm.jpg"
    "dark/street.png"
    "dark/sunken-tower.png"
    "dark/tower.png"
    "dark/train-sideview.png"
    "dark/train-station.jpg"
    "dark/tree.jpg"
    "dark/tree-stump.jpg"
    "dark/trippy-purple.png"
    "dark/van-chilling.png"
    "dark/venice-market.png"
    "dark/voxel-city.jpg"
    "dark/waterfall.png"
  ];
in

stdenvNoCC.mkDerivation (finalAttrs: {
  inherit name src;

  installPhase = ''
    runHook preInstall

    ${lib.getExe lutgen} apply -p catppuccin-mocha *.{png,jpg} -o dark -- "#00a896"
    ${lib.getExe lutgen} apply -p catppuccin-latte *.{png,jpg} -o light -- "#00a896"

    imgdir="${placeholder "out"}/share/wallpapers/assets/contents/images"
    mkdir -p $imgdir
    cp -r * $imgdir

    mkdir -p $imgdir/cycle
    ${builtins.concatStringsSep "\n" (map (file: "cp -v ${file} $imgdir/cycle") cycle)}

    runHook postInstall
  '';
})
