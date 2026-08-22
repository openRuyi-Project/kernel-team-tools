# openEuler-layout kernel spec template for kernel-team-tools/rpm-build.
# Values are injected via rpmbuild --define kb_* parameters.
%global Arch %{?kb_arch}%{?!kb_arch:riscv}
%global KernelVer %{version}-%{release}.%{_target_cpu}
%bcond_with ktools
%bcond_with devel
%bcond_with source

Name:           kernel
Version:        %{?kb_version}%{?!kb_version:0.0.0}
Release:        %{?kb_release}%{?!kb_release:1}%{?dist}
Summary:        The Linux Kernel (openEuler layout)
License:        GPL-2.0-only
URL:            https://www.kernel.org/
Source0:        %{?kb_tarball}
Source1:        rpm-build.config
ExclusiveArch:  %{?kb_rpmarch}

%description
The Linux kernel, packaged in the openEuler layout, built from
%{SOURCE0} by kernel-team-tools/rpm-build.

%package devel
Summary:        Development files for building external kernel modules
Requires:       %{name} = %{version}-%{release}

%description devel
Header files and Makefiles for building external kernel modules against
%{KernelVer}.

%package source
Summary:        Source code for the %{version} kernel
Requires:       %{name} = %{version}-%{release}
Autoreq:        no

%description source
The source code for the %{version} kernel, installed in
/usr/src/linux-%{KernelVer}.

%prep
%setup -q -n linux-%{?kb_srcver}

%build
sed -i "s/^EXTRAVERSION.*/EXTRAVERSION = -%{release}.%{_target_cpu}/" Makefile
sed -i "s/^SUBLEVEL.*/SUBLEVEL = 0/" Makefile

cp %{SOURCE1} .config
make ARCH=%{Arch} olddefconfig

TargetImage=$(basename $(make ARCH=%{Arch} -s image_name))
make ARCH=%{Arch} $TargetImage %{?_smp_mflags}
make ARCH=%{Arch} modules %{?_smp_mflags}
%ifarch riscv64 aarch64
make ARCH=%{Arch} dtbs %{?_smp_mflags}
%endif

%install
mkdir -p $RPM_BUILD_ROOT/boot
install -m 755 $(make ARCH=%{Arch} -s image_name) $RPM_BUILD_ROOT/boot/vmlinuz-%{KernelVer}
install -m 644 .config $RPM_BUILD_ROOT/boot/config-%{KernelVer}
install -m 644 System.map $RPM_BUILD_ROOT/boot/System.map-%{KernelVer}
gzip -c9 < Module.symvers > $RPM_BUILD_ROOT/boot/symvers-%{KernelVer}.gz
%ifarch riscv64 aarch64
make ARCH=%{Arch} INSTALL_DTBS_PATH=$RPM_BUILD_ROOT/lib/modules/%{KernelVer}/dtb dtbs_install
cp -r $RPM_BUILD_ROOT/lib/modules/%{KernelVer}/dtb $RPM_BUILD_ROOT/boot/dtb-%{KernelVer}
%endif

make ARCH=%{Arch} INSTALL_MOD_PATH=$RPM_BUILD_ROOT INSTALL_MOD_STRIP=1 DEPMOD=true modules_install KERNELRELEASE=%{KernelVer}
rm -f $RPM_BUILD_ROOT/lib/modules/%{KernelVer}/build
rm -f $RPM_BUILD_ROOT/lib/modules/%{KernelVer}/source

%if %{with devel}
mkdir -p $RPM_BUILD_ROOT/usr/src/kernels/%{KernelVer}
make ARCH=%{Arch} run-command KBUILD_RUN_COMMAND="$(pwd)/scripts/package/install-extmod-build $RPM_BUILD_ROOT/usr/src/kernels/%{KernelVer}"
ln -sf /usr/src/kernels/%{KernelVer} $RPM_BUILD_ROOT/lib/modules/%{KernelVer}/build
ln -sf /usr/src/kernels/%{KernelVer} $RPM_BUILD_ROOT/lib/modules/%{KernelVer}/source
%endif

%if %{with source}
mkdir -p $RPM_BUILD_ROOT/usr/src/linux-%{KernelVer}
tar -c $(git ls-files 2>/dev/null || find . -type f | sed 's|^\./||') \
    --exclude=./.config | tar -x -C $RPM_BUILD_ROOT/usr/src/linux-%{KernelVer}
%endif

%post
%{_sbindir}/new-kernel-pkg --package kernel --mkinitrd --dracut --depmod --update %{KernelVer} || exit $?

%preun
if [ -x %{_sbindir}/new-kernel-pkg ]; then
    %{_sbindir}/new-kernel-pkg --rminitrd --rmmoddep --remove %{KernelVer} || exit $?
fi

%files
%defattr (-, root, root)
/boot/config-%{KernelVer}
/boot/symvers-%{KernelVer}.gz
/boot/System.map-%{KernelVer}
/boot/vmlinuz-%{KernelVer}
%ghost /boot/initramfs-%{KernelVer}.img
%ifarch riscv64 aarch64
/boot/dtb-%{KernelVer}
%endif
/lib/modules/%{KernelVer}

%if %{with devel}
%files devel
/usr/src/kernels/%{KernelVer}/
/lib/modules/%{KernelVer}/build
/lib/modules/%{KernelVer}/source
%endif

%if %{with source}
%files source
/usr/src/linux-%{KernelVer}/
%endif

%changelog
* %{?kb_changelog_date} kernel-team-tools <noreply@openruyi.cn> - %{version}-%{release}
- Locally generated RPM package from kernel source directory
