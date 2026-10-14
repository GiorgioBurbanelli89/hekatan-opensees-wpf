// ===== Visor 3D orbitable de la deformada OpenSees (vtk.js, offline/GPU, estilo STKO) =====
// Reemplaza el canvas plano para modelos ndm==3: se orbita con el mouse (trackball),
// color jet_r por |u|, estructura sin deformar en gris fantasma, triada de ejes,
// colorbar y hover (datatip) que muestra el nudo mas cercano. Sin internet.
// Cada grafica llama window.osvtkMount(DATA) con su propio contenedor #DATA.gid.
(function () {
  const V = window.vtk;
  if (!V) { return; }
  const vtkGRW   = V.Rendering.Misc.vtkGenericRenderWindow;
  const vtkPoly  = V.Common.DataModel.vtkPolyData;
  const vtkMapper = V.Rendering.Core.vtkMapper;
  const vtkActor  = V.Rendering.Core.vtkActor;
  const vtkDA    = V.Common.Core.vtkDataArray;
  const vtkLUT   = V.Common.Core.vtkLookupTable;
  const vtkBar   = V.Rendering.Core.vtkScalarBarActor;
  const vtkAxes  = V.Rendering.Core.vtkAxesActor;
  const vtkOMW   = V.Interaction.Widgets.vtkOrientationMarkerWidget;
  const vtkPointPicker = V.Rendering.Core.vtkPointPicker;

  // LUT jet_r (igual que la deformada 2D: min |u| = rojo, max = azul). Nunca jet normal.
  function jetR(umax) {
    const lut = vtkLUT.newInstance();
    lut.setNumberOfColors(256);
    lut.setHueRange(0.0, 0.667);   // 0=rojo (poco u) .. 0.667=azul (mucho u)  => jet invertido
    lut.setSaturationRange(1.0, 1.0);
    lut.setValueRange(1.0, 1.0);
    lut.build();
    lut.setRange(0, Math.max(1e-12, umax));
    return lut;
  }

  window.osvtkMount = function (D) {
    const el = document.getElementById(D.gid);
    if (!el) { return; }

    const grw = vtkGRW.newInstance({ background: [1, 1, 1] });
    grw.setContainer(el);
    const ren = grw.getRenderer(), rw = grw.getRenderWindow();

    const lut = jetR(D.umax);

    // ---- deformada (lineas de frames + caras de shells/bricks) coloreada por |u| ----
    const pd = vtkPoly.newInstance();
    pd.getPoints().setData(Float32Array.from(D.pts), 3);
    if (D.lines && D.lines.length) pd.getLines().setData(Uint32Array.from(D.lines));
    if (D.polys && D.polys.length) pd.getPolys().setData(Uint32Array.from(D.polys));
    const umag = vtkDA.newInstance({ name: '|u|', numberOfComponents: 1, values: Float32Array.from(D.umag) });
    pd.getPointData().setScalars(umag);
    const map = vtkMapper.newInstance();
    map.setInputData(pd); map.setLookupTable(lut);
    map.setScalarVisibility(true); map.setScalarRange(0, Math.max(1e-12, D.umax));
    map.setInterpolateScalarsBeforeMapping(true);
    const act = vtkActor.newInstance(); act.setMapper(map);
    act.getProperty().setLineWidth(3);
    act.getProperty().setEdgeVisibility(true);
    act.getProperty().setEdgeColor(0.15, 0.17, 0.20);
    ren.addActor(act);

    // ---- estructura sin deformar (gris fantasma, wireframe) ----
    const pd0 = vtkPoly.newInstance();
    pd0.getPoints().setData(Float32Array.from(D.pts0), 3);
    if (D.lines && D.lines.length) pd0.getLines().setData(Uint32Array.from(D.lines));
    if (D.polys && D.polys.length) pd0.getPolys().setData(Uint32Array.from(D.polys));
    const map0 = vtkMapper.newInstance(); map0.setInputData(pd0); map0.setScalarVisibility(false);
    const act0 = vtkActor.newInstance(); act0.setMapper(map0);
    act0.getProperty().setRepresentation(1);      // 1 = wireframe
    act0.getProperty().setColor(0.72, 0.75, 0.78);
    act0.getProperty().setLineWidth(1);
    act0.getProperty().setOpacity(0.9);
    ren.addActor(act0);

    // ---- colorbar (barra de escala) ----
    try {
      const bar = vtkBar.newInstance();
      bar.setScalarsToColors(lut);
      bar.setAxisLabel('|u| (m)');
      bar.setDrawNanAnnotation(false);
      ren.addActor(bar);
    } catch (e) { /* colorbar opcional */ }

    // ---- triada de ejes (marcador de orientacion en la esquina) ----
    try {
      const axes = vtkAxes.newInstance();
      const omw = vtkOMW.newInstance({ actor: axes, interactor: rw.getInteractor() });
      omw.setEnabled(true);
      omw.setViewportCorner(vtkOMW.Corners.BOTTOM_LEFT);
      omw.setViewportSize(0.15);
    } catch (e) { /* triada opcional */ }

    // ---- camara oblicua desde arriba-frente (como STKO) ----
    ren.resetCamera();
    const cam = ren.getActiveCamera();
    const fp = cam.getFocalPoint(), dist = cam.getDistance();
    cam.setViewUp(0, 0, 1);
    cam.setPosition(fp[0] + dist * 0.65, fp[1] - dist * 0.75, fp[2] + dist * 0.55);
    ren.resetCameraClippingRange();
    grw.resize();
    rw.render();

    // handle del visor (para dirigir la cámara desde verificación / futuro --shot)
    window.__osvtk = { renderWindow: rw, renderer: ren, camera: cam, grw: grw };

    // ---- hover: nudo mas cercano -> datatip que sigue al cursor (valores en vertical) ----
    const tip = document.getElementById(D.gid + '_tip');
    if (tip) {
      const picker = vtkPointPicker.newInstance();
      picker.setPickFromList(false);
      const interactor = rw.getInteractor();
      const fx = (v) => (Math.abs(v) < 1e-4 && v !== 0) ? v.toExponential(3) : v.toFixed(5);
      interactor.onMouseMove((cd) => {
        const p = cd.position;
        picker.pick([p.x, p.y, 0], ren);
        const id = picker.getPointId();
        if (id != null && id >= 0 && id < D.tags.length) {
          const u = D.uvec[id] || [0, 0, 0];
          tip.style.display = 'block';
          tip.style.left = (p.x + 14) + 'px';
          tip.style.bottom = (p.y + 14) + 'px';   // vtk y = desde abajo
          tip.innerHTML = 'nudo ' + D.tags[id] +
            '<br>ux = ' + fx(u[0]) + '<br>uy = ' + fx(u[1]) + '<br>uz = ' + fx(u[2] || 0) +
            '<br>|u| = ' + fx(D.umag[id]);
        } else {
          tip.style.display = 'none';
        }
      });
    }
  };
})();
