// GERMANY VEGETATION ANOMALY PROJECT
// FINAL FIXED-LAND-COVER EXPORT — PROJECTION FIXED
// Recovered final extraction workflow. A fresh 2001 rerun reproduced the
// archived manuscript export to floating-point precision.

// 1. STUDY AREA
var germany = ee.FeatureCollection('FAO/GAUL/2015/level1')
  .filter(ee.Filter.eq('ADM0_NAME', 'Germany'));
print('German ADM1 count:', germany.size());
print('German ADM1 names:', germany.aggregate_array('ADM1_NAME').sort());
var germanyGeometry = germany.geometry();
var processingRegion = germanyGeometry.buffer(5000).bounds();
var stateList = germany.toList(germany.size());

// 2. MOD13A3 REFERENCE PROJECTION
var modisReference = ee.ImageCollection('MODIS/061/MOD13A3')
  .filterDate('2001-01-01', '2001-02-01').first().select('NDVI');
var modisProjection = modisReference.projection();
print('MOD13A3 nominal scale:', modisProjection.nominalScale());

// 3. MCD12Q1 NATIVE PROJECTION
// The temporal mode later loses a usable default projection, so the native
// MCD12Q1 projection is retained and restored explicitly.
var mcdReference = ee.ImageCollection('MODIS/061/MCD12Q1')
  .filterDate('2001-01-01', '2002-01-01').first().select('LC_Type1');
var mcdProjection = mcdReference.projection();
print('MCD12Q1 native projection:', mcdProjection);
print('MCD12Q1 nominal scale:', mcdProjection.nominalScale());

// 4. MOD13A3 MONTHLY NDVI — 2001–2024
var modis = ee.ImageCollection('MODIS/061/MOD13A3')
  .filterDate('2001-01-01', '2025-01-01')
  .filterBounds(germany)
  .map(function(img) {
    var qa = img.select('SummaryQA');
    var qaMask = qa.lte(1);
    var ndvi = img.select('NDVI').multiply(0.0001)
      .updateMask(qaMask).rename('ndvi');
    return ndvi.copyProperties(img, ['system:time_start']);
  });
print('MOD13A3 monthly images:', modis.size());

// 5. ERA5-LAND MONTHLY — 2001–2024
var era5 = ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
  .filterDate('2001-01-01', '2025-01-01')
  .filterBounds(germany)
  .select([
    'temperature_2m',
    'volumetric_soil_water_layer_1',
    'total_precipitation_sum'
  ])
  .map(function(img) {
    var temp = img.select('temperature_2m').subtract(273.15).rename('temp_c');
    var sm = img.select('volumetric_soil_water_layer_1').rename('soil_moisture');
    var pr = img.select('total_precipitation_sum').multiply(1000).rename('precip_mm');
    return temp.addBands(sm).addBands(pr).resample('bilinear')
      .copyProperties(img, ['system:time_start']);
  });
print('ERA5-Land monthly images:', era5.size());

// 6. MCD12Q1 REFERENCE PERIOD — 2001–2016
var lcReference = ee.ImageCollection('MODIS/061/MCD12Q1')
  .filterDate('2001-01-01', '2017-01-01')
  .filterBounds(germany);
print('MCD12Q1 reference images:', lcReference.size());

// 7. RECLASSIFY EACH REFERENCE YEAR
function simplifyReferenceYear(img) {
  var igbp = img.select('LC_Type1');
  var qc = img.select('QC');
  // 1 forest (IGBP 1–5), 2 cropland (12), 3 grassland (10), 0 excluded.
  var broad = igbp.remap(
    [1, 2, 3, 4, 5, 10, 12],
    [1, 1, 1, 1, 1, 3, 2],
    0
  ).rename('lc_simple');
  broad = broad.updateMask(qc.eq(0))
    .clip(processingRegion)
    .setDefaultProjection(mcdProjection);
  return broad.copyProperties(img, ['system:time_start']);
}
var broadReferenceCollection = lcReference.map(simplifyReferenceYear);
print('Broad reference images:', broadReferenceCollection.size());

// 8. FIXED MODAL LAND COVER — 2001–2016
var fixedLc = broadReferenceCollection
  .reduce(ee.Reducer.mode())
  .rename('lc_fixed')
  .setDefaultProjection(mcdProjection)
  .clip(processingRegion);
print('Fixed LC projection:', fixedLc.projection());

// 9. REFERENCE SUPPORT DIAGNOSTIC
var referenceValidYears = broadReferenceCollection
  .map(function(img) {
    return img.mask().reduce(ee.Reducer.min())
      .rename('valid_year')
      .setDefaultProjection(mcdProjection);
  })
  .sum()
  .setDefaultProjection(mcdProjection)
  .rename('reference_valid_years');

// 10. FIXED LC FRACTIONS ON MOD13A3 GRID
function classFractionOnModis(fixedLandCover, classNumber) {
  classNumber = ee.Number(classNumber);
  var binary = fixedLandCover.eq(classNumber)
    .unmask(0).toFloat()
    .setDefaultProjection(mcdProjection)
    .clip(processingRegion);
  return binary.reduceResolution({
      reducer: ee.Reducer.mean(),
      maxPixels: 64,
      bestEffort: false
    })
    .reproject(modisProjection)
    .clip(processingRegion)
    .rename('lc_fraction');
}

// 11. BUILD FIXED FRACTIONS ONCE
var forestFraction = classFractionOnModis(fixedLc, 1).set('lc_class', 1);
var croplandFraction = classFractionOnModis(fixedLc, 2).set('lc_class', 2);
var grasslandFraction = classFractionOnModis(fixedLc, 3).set('lc_class', 3);
var fixedFractions = ee.ImageCollection.fromImages([
  forestFraction, croplandFraction, grasslandFraction
]);

// 12. CONSTANTS
var months = ee.List.sequence(1, 12);
var lcClasses = ee.List([1, 2, 3]);

// 13. BUILD ONE YEAR
function buildYear(yearJS) {
  var year = ee.Number(yearJS);
  var results = months.map(function(monthObject) {
    var month = ee.Number(monthObject);
    var monthStart = ee.Date.fromYMD(year, month, 1);
    var monthEnd = monthStart.advance(1, 'month');

    var ndviImage = modis.filterDate(monthStart, monthEnd)
      .mean().rename('ndvi').setDefaultProjection(modisProjection);
    var climateImage = era5.filterDate(monthStart, monthEnd).mean();

    return stateList.map(function(stateObject) {
      var state = ee.Feature(stateObject);
      var stateName = state.get('ADM1_NAME');
      var stateGeometry = state.geometry();

      return lcClasses.map(function(classObject) {
        var cls = ee.Number(classObject);
        var fraction = ee.Image(
          fixedFractions.filter(ee.Filter.eq('lc_class', cls)).first()
        );

        // Valid NDVI support and fractional class weight.
        var validNdvi = ndviImage.mask().reduce(ee.Reducer.min());
        var supportMask = fraction.gt(0).and(validNdvi);
        var weight = fraction.updateMask(supportMask).rename('weight');
        var ndviSupported = ndviImage.updateMask(supportMask);
        var climateSupported = climateImage.updateMask(supportMask);

        var ndviWeighted = ndviSupported.multiply(weight).rename('ndvi_weighted');
        var tempWeighted = climateSupported.select('temp_c')
          .multiply(weight).rename('temp_weighted');
        var smWeighted = climateSupported.select('soil_moisture')
          .multiply(weight).rename('sm_weighted');
        var precipWeighted = climateSupported.select('precip_mm')
          .multiply(weight).rename('precip_weighted');
        var validPixel = ndviSupported.multiply(0).add(1).rename('valid_pixel');
        var weightedArea = ee.Image.pixelArea().multiply(weight)
          .rename('weighted_area_m2');

        var reductionImage = ndviWeighted
          .addBands(tempWeighted)
          .addBands(smWeighted)
          .addBands(precipWeighted)
          .addBands(weight)
          .addBands(validPixel)
          .addBands(weightedArea);

        // Important: the validated final workflow specifies the MOD13A3
        // projection through `crs` and does not separately set scale/transform.
        var stats = reductionImage.reduceRegion({
          reducer: ee.Reducer.sum(),
          geometry: stateGeometry,
          crs: modisProjection,
          maxPixels: 1e9,
          tileScale: 4
        });

        var weightSum = ee.Number(ee.Algorithms.If(
          ee.Algorithms.IsEqual(stats.get('weight'), null),
          0,
          stats.get('weight')
        ));

        var ndviMean = ee.Algorithms.If(
          weightSum.gt(0),
          ee.Number(stats.get('ndvi_weighted')).divide(weightSum),
          null
        );
        var tempMean = ee.Algorithms.If(
          weightSum.gt(0),
          ee.Number(stats.get('temp_weighted')).divide(weightSum),
          null
        );
        var smMean = ee.Algorithms.If(
          weightSum.gt(0),
          ee.Number(stats.get('sm_weighted')).divide(weightSum),
          null
        );
        var precipMean = ee.Algorithms.If(
          weightSum.gt(0),
          ee.Number(stats.get('precip_weighted')).divide(weightSum),
          null
        );

        var validPixelCount = ee.Number(ee.Algorithms.If(
          ee.Algorithms.IsEqual(stats.get('valid_pixel'), null),
          0,
          stats.get('valid_pixel')
        ));
        var meanFraction = ee.Algorithms.If(
          validPixelCount.gt(0),
          weightSum.divide(validPixelCount),
          null
        );
        var effectiveAreaKm2 = ee.Algorithms.If(
          weightSum.gt(0),
          ee.Number(stats.get('weighted_area_m2')).divide(1000000),
          null
        );

        var lcName = ee.String(ee.Algorithms.If(
          cls.eq(1), 'forest',
          ee.Algorithms.If(cls.eq(2), 'cropland', 'grassland')
        ));

        return ee.Feature(null, {
          year: year,
          month: month,
          adm1: stateName,
          lc_class: cls,
          lc_name: lcName,
          ndvi: ndviMean,
          temp_c: tempMean,
          soil_moisture: smMean,
          precip_mm: precipMean,
          ndvi_n: validPixelCount,
          lc_weight_sum: weightSum,
          lc_fraction_mean: meanFraction,
          lc_area_km2: effectiveAreaKm2
        });
      });
    });
  });
  return ee.FeatureCollection(ee.List(results).flatten());
}

// 14. TEST 2001 FIRST
var test2001 = buildYear(2001);
print('Expected rows for 2001:', 576);
print('2001 FeatureCollection size:', test2001.size());
print('2001 first record:', test2001.first());

// 15. OPTIONAL MAP CHECK
Map.centerObject(germany, 6);
Map.addLayer(fixedLc, {
  min: 0,
  max: 3,
  palette: ['999999', '006400', 'FFD700', '7CFC00']
}, 'Fixed modal LC 2001–2016', false);
Map.addLayer(forestFraction, {min: 0, max: 1}, 'Fixed forest fraction', false);

// 16. CREATE YEARLY EXPORT TASKS
for (var y = 2001; y <= 2024; y++) {
  var annualOutput = buildYear(y);
  var yearString = String(y);
  Export.table.toDrive({
    collection: annualOutput,
    description: 'Germany_FIXEDLC_MODIS_ERA5_' + yearString,
    fileNamePrefix: 'germany_fixedLC_mod13a3_era5_' + yearString,
    fileFormat: 'CSV',
    selectors: [
      'year', 'month', 'adm1', 'lc_class', 'lc_name',
      'ndvi', 'temp_c', 'soil_moisture', 'precip_mm',
      'ndvi_n', 'lc_weight_sum', 'lc_fraction_mean', 'lc_area_km2'
    ]
  });
}
