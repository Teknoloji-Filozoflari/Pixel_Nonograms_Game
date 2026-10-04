%global debug_package %{nil}
%global __os_install_post %{nil}
%global __provides_exclude_from ^/usr/lib/pixel-nonograms/.*$
%global __requires_exclude_from ^/usr/lib/pixel-nonograms/.*$

Name: pixel-nonograms
Version: %{app_version}
Release: 1%{?dist}
Summary: Offline picture logic game with 1000 puzzles
License: LicenseRef-Unknown
URL: https://github.com/Teknoloji-Filozoflari/Pixel_Nonograms_Game
Source0: payload.tar.gz
Requires: glibc >= 2.42
Requires: fontconfig, dbus-libs, mesa-libEGL, mesa-libGL
Requires: libX11, libX11-xcb, libxcb, libxkbcommon, libxkbcommon-x11
Requires: xcb-util-cursor, xcb-util-image, xcb-util-keysyms
Requires: xcb-util-renderutil, xcb-util-wm

%description
Offline monochrome and color nonograms with five languages and local saves.
Python and Qt remain in a private bundle. The project has no declared code
license; existing third-party licenses are included with the application.

%prep
%setup -q -c -T
tar -xf %{SOURCE0}

%build

%install
mkdir -p %{buildroot}
cp -a usr %{buildroot}/

%files
/usr/lib/pixel-nonograms
/usr/bin/pixel-nonograms
/usr/share/applications/pixel-nonograms.desktop
/usr/share/icons/hicolor/256x256/apps/pixel-nonograms.png
/usr/share/doc/pixel-nonograms
